"""AppFolio row dataclasses and CSV/Excel row parsers.

Parses raw ``dict[str, Any]`` rows (from documents/parsers.py) into typed
dataclasses.  All type coercions (float, int, date, bool) happen here so
that adapter.py receives clean, typed values.

Key fix over the old appfolio_schema.py: ``_to_date`` actually parses common
date string formats instead of silently returning None for non-datetime values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from remi.ingestion.adapters.appfolio.schema import RENT_ROLL_SECTIONS

# ---------------------------------------------------------------------------
# Typed row dataclasses
# ---------------------------------------------------------------------------


@dataclass
class RentRollRow:
    property_address: str
    property_name: str
    unit_number: str | None
    # occupied / notice_rented / notice_unrented / vacant_rented / vacant_unrented
    occupancy_status: str
    bedrooms: int | None
    bathrooms: float | None
    lease_start: date | None
    lease_end: date | None
    posted_website: bool
    posted_internet: bool
    days_vacant: int | None
    notes: str | None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class DelinquencyRow:
    tenant_status: str  # Current / Notice / Evict
    property_address: str
    property_name: str
    unit_number: str | None
    tenant_name: str
    monthly_rent: float
    amount_owed: float
    subsidy_delinquent: float
    last_payment_date: date | None
    balance_0_30: float
    balance_30_plus: float
    tags: str | None
    delinquency_notes: str | None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class LeaseExpirationRow:
    tags: str | None
    property_address: str
    property_name: str
    unit_number: str | None
    move_in_date: date | None
    lease_expires: date | None
    monthly_rent: float
    market_rent: float | None
    sqft: int | None
    tenant_name: str
    deposit: float
    phone_numbers: str | None
    is_month_to_month: bool
    raw: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Coercion helpers
# ---------------------------------------------------------------------------

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m/%d/%y",
    "%m-%d-%Y",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%m/%d/%Y %H:%M",
)


def _to_date(val: Any) -> date | None:
    """Coerce a value to ``date``, parsing common string formats.

    Returns None if the value is absent or unparseable — never raises.
    """
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    s = str(val).strip()
    if not s:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _to_float(val: Any) -> float:
    if val is None:
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _to_int(val: Any) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _to_bool(val: Any) -> bool:
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("yes", "true", "1")


# ---------------------------------------------------------------------------
# Property name helpers
# ---------------------------------------------------------------------------


def parse_property_name(full_address: str) -> str:
    """Extract short property name from AppFolio's 'Name - Full Address' format.

    AppFolio encodes property addresses as either:
      '1018 Woodbourne Avenue - 1018 Woodbourne Avenue Pittsburgh, PA 15226'
    or just:
      '142 S. 19th Street Pittsburgh, PA 15203'

    Returns the part before the dash, or the first comma-delimited segment.
    """
    if not full_address:
        return full_address
    if " - " in full_address:
        return full_address.split(" - ")[0].strip()
    parts = full_address.split(",")
    if len(parts) >= 2:
        return parts[0].strip()
    return full_address.strip()


def parse_bd_ba(bd_ba: str | None) -> tuple[int | None, float | None]:
    """Parse AppFolio BD/BA field like '3/1.00', '2/2.50', '--/--'.

    Returns (bedrooms, bathrooms).
    """
    if not bd_ba or bd_ba == "--/--":
        return None, None
    try:
        parts = str(bd_ba).split("/")
        beds = int(parts[0]) if parts[0].strip() != "--" else None
        baths = float(parts[1]) if len(parts) > 1 and parts[1].strip() != "--" else None
        return beds, baths
    except (ValueError, IndexError):
        return None, None


# ---------------------------------------------------------------------------
# Section-aware Rent Roll parsing
# ---------------------------------------------------------------------------


def parse_rent_roll_rows(raw_rows: list[dict[str, Any]]) -> list[RentRollRow]:
    """Parse all data rows from a rent roll document, tracking occupancy sections.

    Section header rows (e.g. ``{'Property': 'Current', ...}``) set the
    occupancy_status for all subsequent rows until the next section.
    Count summary rows (e.g. ``{'Unit': '136 Units'}``) are skipped.
    """
    results: list[RentRollRow] = []
    current_section = "occupied"

    for row in raw_rows:
        property_val = row.get("Property") or row.get("property_address") or ""
        unit_val = row.get("Unit") or row.get("unit_number")

        if str(property_val).strip() in RENT_ROLL_SECTIONS:
            current_section = RENT_ROLL_SECTIONS[str(property_val).strip()]
            continue

        if property_val is None and unit_val and str(unit_val).endswith("Units"):
            continue
        if not property_val or str(property_val).strip() == "":
            continue

        beds, baths = parse_bd_ba(row.get("BD/BA") or row.get("bd_ba"))

        results.append(
            RentRollRow(
                property_address=str(property_val),
                property_name=parse_property_name(str(property_val)),
                unit_number=str(unit_val).strip() if unit_val else None,
                occupancy_status=current_section,
                bedrooms=beds,
                bathrooms=baths,
                lease_start=_to_date(row.get("Lease From") or row.get("lease_start")),
                lease_end=_to_date(row.get("Lease To") or row.get("lease_end")),
                posted_website=_to_bool(row.get("Posted To Website") or row.get("posted_website")),
                posted_internet=_to_bool(
                    row.get("Posted To Internet") or row.get("posted_internet")
                ),
                days_vacant=_to_int(row.get("Days Vacant") or row.get("days_vacant")),
                notes=str(row.get("Description") or row.get("notes") or "").strip() or None,
                raw=row,
            )
        )

    return results


def parse_delinquency_rows(raw_rows: list[dict[str, Any]]) -> list[DelinquencyRow]:
    """Parse all data rows from a delinquency document."""
    results: list[DelinquencyRow] = []

    for row in raw_rows:
        property_val = row.get("Property") or row.get("property_address") or ""
        if not property_val or str(property_val).strip() == "":
            continue

        unit_val = row.get("Unit") or row.get("unit_number")
        tenant_name = str(row.get("Name") or row.get("tenant_name") or "").strip()
        if not tenant_name:
            continue

        results.append(
            DelinquencyRow(
                tenant_status=str(
                    row.get("Tenant Status") or row.get("tenant_status") or ""
                ).strip(),
                property_address=str(property_val),
                property_name=parse_property_name(str(property_val)),
                unit_number=str(unit_val).strip() if unit_val else None,
                tenant_name=tenant_name,
                monthly_rent=_to_float(row.get("Rent") or row.get("monthly_rent")),
                amount_owed=_to_float(row.get("Amount Receivable") or row.get("amount_owed")),
                subsidy_delinquent=_to_float(
                    row.get("Delinquent Subsidy Amount") or row.get("subsidy_delinquent")
                ),
                last_payment_date=_to_date(
                    row.get("Last Payment") or row.get("last_payment_date")
                ),
                balance_0_30=_to_float(row.get("0-30") or row.get("balance_0_30")),
                balance_30_plus=_to_float(row.get("30+") or row.get("balance_30_plus")),
                tags=str(row.get("Tags") or row.get("tags") or "").strip() or None,
                delinquency_notes=str(
                    row.get("Delinquency Notes") or row.get("delinquency_notes") or ""
                ).strip()
                or None,
                raw=row,
            )
        )

    return results


def parse_lease_expiration_rows(raw_rows: list[dict[str, Any]]) -> list[LeaseExpirationRow]:
    """Parse all data rows from a lease expiration document.

    Section headers (rows where both property and tenant are empty) set the
    month-to-month flag for subsequent rows.
    """
    results: list[LeaseExpirationRow] = []
    current_is_mtm = False

    for row in raw_rows:
        tags_val = str(row.get("Tags") or row.get("tags") or "").strip()
        property_val = row.get("Property") or row.get("property_address") or ""
        tenant_val = str(row.get("Tenant Name") or row.get("tenant_name") or "").strip()

        is_section_header = not str(property_val).strip() and not tenant_val
        if is_section_header:
            current_is_mtm = tags_val == "Month-To-Month"
            continue

        if not str(property_val).strip() or not tenant_val:
            continue

        unit_val = row.get("Unit") or row.get("unit_number")
        lease_expires_val = row.get("Lease Expires") or row.get("lease_expires")

        results.append(
            LeaseExpirationRow(
                tags=tags_val or None,
                property_address=str(property_val),
                property_name=parse_property_name(str(property_val)),
                unit_number=str(unit_val).strip() if unit_val else None,
                move_in_date=_to_date(row.get("Move In") or row.get("move_in_date")),
                lease_expires=_to_date(lease_expires_val),
                monthly_rent=_to_float(row.get("Rent") or row.get("monthly_rent")),
                market_rent=_to_float(row.get("Market Rent") or row.get("market_rent")) or None,
                sqft=_to_int(row.get("Sqft") or row.get("sqft")),
                tenant_name=tenant_val,
                deposit=_to_float(row.get("Deposit") or row.get("deposit")),
                phone_numbers=str(
                    row.get("Phone Numbers") or row.get("phone_numbers") or ""
                ).strip()
                or None,
                is_month_to_month=current_is_mtm or (lease_expires_val is None),
                raw=row,
            )
        )

    return results
