"""Rule-based report extraction — deterministic, zero-LLM fallback.

Detects report type from column headers, maps raw column names to the
field names the persistence layer expects, and classifies each row with
the entity ``type`` the persisters understand.

Pipeline order:  rules-based  →  LLM fallback

If the rule engine recognises the report, it returns extracted rows
directly — no API calls, no credits, no latency.  If it can't match,
returns ``None`` so the caller can fall through to LLM.
"""

from __future__ import annotations

from typing import Any

import structlog

_log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Column-signature → report type detection
# ---------------------------------------------------------------------------

_SIGNATURES: list[tuple[str, frozenset[str], str]] = [
    # (report_type, required_lower_columns, row_entity_type)
    (
        "rent_roll",
        frozenset({"property", "unit", "lease from", "lease to"}),
        "Unit",
    ),
    (
        "delinquency",
        frozenset({"property", "name", "amount receivable"}),
        "Tenant",
    ),
    (
        "lease_expiration",
        frozenset({"property", "lease expires", "tenant name"}),
        "Lease",
    ),
    (
        "property_directory",
        frozenset({"property"}),
        "Property",
    ),
]


def detect_report_type(
    columns: list[str],
) -> tuple[str, str] | None:
    """Return ``(report_type, entity_type)`` or ``None``."""
    lower = {c.lower().strip() for c in columns}
    for report_type, required, entity_type in _SIGNATURES:
        if required <= lower:
            return report_type, entity_type
    return None


# ---------------------------------------------------------------------------
# Per-report-type column mappings  (raw_column → persister field)
# ---------------------------------------------------------------------------

_RENT_ROLL_MAP: dict[str, str] = {
    "Property": "property_address",
    "Unit": "unit_number",
    "BD/BA": "_bd_ba",
    "Beds": "bedrooms",
    "Baths": "bathrooms",
    "Sq Ft": "sqft",
    "Lease From": "lease_start",
    "Lease To": "lease_end",
    "Rent": "monthly_rent",
    "Market Rent": "market_rent",
    "Revenue": "_revenue_flag",
    "Days Vacant": "days_vacant",
    "Description": "description",
    "Status": "occupancy_status",
    "Posted To Website": "posted_website",
    "Posted To Internet": "posted_internet",
    "Tags": "tags",
}

_DELINQUENCY_MAP: dict[str, str] = {
    "Tenant Status": "tenant_status",
    "Property": "property_address",
    "Unit": "unit_number",
    "Name": "name",
    "Rent": "monthly_rent",
    "Amount Receivable": "amount_owed",
    "Delinquent Subsidy Amount": "_subsidy",
    "Last Payment": "last_payment_date",
    "0-30": "balance_0_30",
    "30+": "balance_30_plus",
    "Tags": "_lease_tags",
    "Delinquency Notes": "delinquency_notes",
}

_LEASE_EXPIRATION_MAP: dict[str, str] = {
    "Tags": "tags",
    "Property": "property_address",
    "Unit": "unit_number",
    "Move In": "move_in_date",
    "Lease Expires": "lease_expires",
    "Rent": "monthly_rent",
    "Market Rent": "market_rent",
    "Sqft": "sqft",
    "Tenant Name": "tenant_name",
    "Deposit": "deposit",
    "Phone Numbers": "phone_numbers",
}

_PROPERTY_DIRECTORY_MAP: dict[str, str] = {
    "Property": "property_address",
    "Units": "_unit_count",
    "Site Manager Name": "site_manager_name",
    "Property Manager": "site_manager_name",
    "Manager Name": "site_manager_name",
    "Assigned Manager": "site_manager_name",
}

_COLUMN_MAPS: dict[str, dict[str, str]] = {
    "rent_roll": _RENT_ROLL_MAP,
    "delinquency": _DELINQUENCY_MAP,
    "lease_expiration": _LEASE_EXPIRATION_MAP,
    "property_directory": _PROPERTY_DIRECTORY_MAP,
}


# ---------------------------------------------------------------------------
# Section header filtering
# ---------------------------------------------------------------------------

_SECTION_HEADERS = frozenset({
    "current", "vacant", "notice", "past", "future", "eviction",
    "month-to-month", "total", "grand total", "subtotal",
    "vacant-unrented", "vacant-rented", "notice-unrented", "notice-rented",
})

_JUNK_PREFIXES = (
    "1234 ", "1234-", "auto loan", "bank reconciliation", "citizens corporate",
    "fnb corporate", "gordon garage", "pbc supply", "ramp", "riva ridge corporate",
    "sycamore lot", "vail",
)

_JUNK_CONTAINS = frozenset({
    "holiday", "pto", "morning meeting", "renovation meeting",
    "staging", "must enter address", "outside project",
})


def _is_junk_property(address: str) -> bool:
    """AppFolio internal bookkeeping entries that aren't real properties."""
    lower = address.lower()
    if any(lower.startswith(p) for p in _JUNK_PREFIXES):
        return True
    return any(kw in lower for kw in _JUNK_CONTAINS)


def _normalize_address(address: str) -> str:
    """Strip 'DO NOT USE' prefixes so addresses match across reports."""
    stripped = address
    for prefix in ("DO NOT USE - ", "DO NOT USE-", "DO NOT USE "):
        if stripped.upper().startswith(prefix.upper()):
            stripped = stripped[len(prefix):].strip()
            break
    return stripped


def _is_section_header(row: dict[str, Any], property_key: str) -> bool:
    prop = str(row.get(property_key) or "").strip().lower()
    if prop in _SECTION_HEADERS:
        return True
    non_empty = sum(1 for v in row.values() if v is not None and str(v).strip())
    return non_empty <= 1 and not prop


# ---------------------------------------------------------------------------
# BD/BA splitter
# ---------------------------------------------------------------------------

def _split_bd_ba(val: str) -> tuple[int | None, float | None]:
    """Parse '2/1' or '3 / 2.5' into (bedrooms, bathrooms)."""
    val = val.strip()
    if not val:
        return None, None
    for sep in ("/", "|"):
        if sep in val:
            parts = val.split(sep, 1)
            try:
                beds = int(parts[0].strip())
            except (ValueError, TypeError):
                beds = None
            try:
                baths = float(parts[1].strip())
            except (ValueError, TypeError):
                baths = None
            return beds, baths
    return None, None


# ---------------------------------------------------------------------------
# Occupancy inference from section context
# ---------------------------------------------------------------------------

_STATUS_KEYWORDS: dict[str, str] = {
    "current": "occupied",
    "vacant-unrented": "vacant_unrented",
    "vacant-rented": "vacant_rented",
    "vacant": "vacant_unrented",
    "notice-unrented": "notice_unrented",
    "notice-rented": "notice_rented",
    "notice": "notice_unrented",
    "month-to-month": "occupied",
    "eviction": "occupied",
    "past": "vacant_unrented",
    "future": "vacant_rented",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_rows(
    columns: list[str],
    rows: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]] | None:
    """Try rule-based extraction. Returns ``(report_type, mapped_rows)`` or ``None``.

    Each returned row has a ``"type"`` key (``Unit``, ``Tenant``, ``Lease``,
    ``Property``) plus all the field names the persisters expect.
    """
    match = detect_report_type(columns)
    if match is None:
        return None

    report_type, entity_type = match
    col_map = _COLUMN_MAPS.get(report_type)
    if col_map is None:
        return None

    property_key = next(
        (raw for raw, mapped in col_map.items() if mapped == "property_address"),
        "Property",
    )

    mapped: list[dict[str, Any]] = []
    current_status: str | None = None
    junk_count = 0

    for raw_row in rows:
        prop_val = str(raw_row.get(property_key) or "").strip()
        prop_lower = prop_val.lower()

        if prop_lower in _STATUS_KEYWORDS:
            current_status = _STATUS_KEYWORDS[prop_lower]
            continue

        if _is_section_header(raw_row, property_key):
            continue

        if not prop_val:
            continue

        prop_val = _normalize_address(prop_val)

        if _is_junk_property(prop_val):
            junk_count += 1
            continue

        out: dict[str, Any] = {"type": entity_type}

        for raw_col, field_name in col_map.items():
            val = raw_row.get(raw_col)
            if val is None:
                continue
            if field_name.startswith("_"):
                continue
            out[field_name] = val

        if "property_address" in out:
            out["property_address"] = _normalize_address(str(out["property_address"]))

        if "_bd_ba" in col_map:
            bd_ba_raw = str(raw_row.get("BD/BA") or "").strip()
            if bd_ba_raw:
                beds, baths = _split_bd_ba(bd_ba_raw)
                if beds is not None:
                    out["bedrooms"] = beds
                if baths is not None:
                    out["bathrooms"] = baths

        if report_type == "rent_roll" and current_status and "occupancy_status" not in out:
            out["occupancy_status"] = current_status

        if report_type == "property_directory":
            mgr = out.get("site_manager_name") or ""
            if mgr:
                out["manager_name"] = mgr

        mapped.append(out)

    if junk_count:
        _log.info("rules_junk_filtered", report_type=report_type, count=junk_count)

    if not mapped:
        _log.warning(
            "rules_extraction_empty",
            report_type=report_type,
            raw_row_count=len(rows),
        )
        return None

    _log.info(
        "rules_extraction_complete",
        report_type=report_type,
        entity_type=entity_type,
        extracted=len(mapped),
        skipped=len(rows) - len(mapped),
    )
    return report_type, mapped
