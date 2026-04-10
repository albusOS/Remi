"""Ingestion utility functions — domain knowledge for the pipeline execution layer.

Junk filtering, address normalization, BD/BA parsing, section header detection,
type coercion (date/decimal/int), and enum maps.

Column classification and mapping is handled by the ingester agent (LLM).
These utilities are called by the pipeline execution layer (operations.py)
after the agent has produced a column_map.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import structlog

from remi.application.core.models.address import Address
from remi.application.core.models.enums import (
    MaintenanceStatus,
    Priority,
    TenantStatus,
    TradeCategory,
)

_log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Junk property filtering
# AppFolio internal bookkeeping entries that are not real rental properties.
# Rows like "1234 Morning Meeting" or "Auto Loan" are internal categories,
# not physical addresses.  "DO NOT USE" and "ZEROED OUT" are real addresses
# that the company has deactivated — those are handled separately as
# inactive properties, not junk.
# ---------------------------------------------------------------------------

_JUNK_PREFIXES = (
    "1234 ",
    "1234-",
    "2022 holiday",
    "auto loan",
    "bank reconciliation",
    "citizens corporate",
    "fnb corporate",
    "gordon garage",
    "pbc supply",
    "ramp",
    "riva ridge corporate",
    "sycamore lot",
    "vail",
)

_JUNK_EXACT = frozenset(
    {
        "total",
        "grand total",
        "subtotal",
        "totals",
    }
)

_JUNK_CONTAINS = frozenset(
    {
        "pto",
        "morning meeting",
        "renovation meeting",
        "staging",
        "must enter address",
        "outside project",
    }
)

# Prefixes that mark real physical properties as inactive/deactivated in
# AppFolio.  We strip the prefix, create the property, and flag its status.
_INACTIVE_PREFIXES = (
    "DO NOT USE - ",
    "DO NOT USE-",
    "DO NOT USE ",
    "ZEROED OUT - ",
    "ZEROED OUT-",
    "ZEROED OUT ",
)


def is_junk_property(address: str) -> bool:
    """True when the address is an AppFolio internal bookkeeping entry.

    Does NOT flag "DO NOT USE" or "ZEROED OUT" addresses — those are real
    properties with an inactive status marker.
    """
    lower = address.lower().strip()
    if lower in _JUNK_EXACT:
        return True
    if any(lower.startswith(p) for p in _JUNK_PREFIXES):
        return True
    return any(kw in lower for kw in _JUNK_CONTAINS)


def is_inactive_property(address: str) -> bool:
    """True when the raw address carries a deactivation prefix.

    The property is real but marked inactive in AppFolio.
    """
    upper = address.upper().strip()
    return any(upper.startswith(p.upper()) for p in _INACTIVE_PREFIXES)


# ---------------------------------------------------------------------------
# Address normalization
# ---------------------------------------------------------------------------

# AppFolio property directory format: "<display label> - <full address>"
# The label is always a prefix of the address, e.g.:
#   "1 Crosman St - 1 Crosman St Pittsburgh, PA 15203"
#   "1 Pius Street - C6 - 1 Pius Street Unit C6 Pittsburgh, PA 15203"
#   "101-103 E Agnew Avenue - 101-103 E Agnew Avenue Pittsburgh, PA 15210"
#
# Strategy: try every " - " split point; if the part after the split starts
# with the label (case-insensitive), the label is redundant — strip it.
# We scan left-to-right so the first matching split wins (shortest label).
#
# Handles the tricky unit-suffix case:
#   "1 Pius Street - C6 - 1 Pius Street Unit C6 Pittsburgh, PA 15203"
#   Split 1: label="1 Pius Street", remainder="C6 - 1 Pius Street Unit C6..."
#            → no match (remainder starts with "C6", not "1 Pius")
#   Split 2: label="1 Pius Street - C6", remainder="1 Pius Street Unit C6..."
#            → no match (label has " - " in it, remainder doesn't start with it)
# For this pattern the remainder after the LAST " - " is the canonical address:
#   "1 Pius Street Unit C6 Pittsburgh, PA 15203"
# So if no early split matches, we also try: does stripping everything up to
# the last " - " produce a remainder that starts with a street number?
def _strip_appfolio_label(address: str) -> str:
    sep = " - "
    start = 0
    while True:
        idx = address.find(sep, start)
        if idx == -1:
            break
        label = address[:idx].strip()
        remainder = address[idx + len(sep) :]
        if label and remainder.lower().startswith(label.lower()):
            return remainder.strip()
        start = idx + len(sep)

    # Fallback: if the string has multiple " - " segments and the last segment
    # starts with a digit (street number), take it — it's the canonical address.
    last_idx = address.rfind(sep)
    if last_idx > 0:
        last_part = address[last_idx + len(sep) :].strip()
        if last_part and last_part[0].isdigit():
            return last_part

    return address


def normalize_address(address: str) -> str:
    """Strip AppFolio label prefixes and deactivation markers from addresses."""
    address = _strip_appfolio_label(address)
    for prefix in _INACTIVE_PREFIXES:
        if address.upper().startswith(prefix.upper()):
            return address[len(prefix) :].strip()
    return address


# ---------------------------------------------------------------------------
# BD/BA parsing
# ---------------------------------------------------------------------------


def split_bd_ba(val: str) -> tuple[int | None, float | None]:
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
# Manager tag validation
# AppFolio Tags columns contain a mix of real manager names and lease-level
# labels ("Section 8", "MTM", "12 Month Renewal - $25 Rent Increase").
# This guard prevents lease tags from creating fake managers.
# ---------------------------------------------------------------------------

_MANAGER_SUFFIXES = frozenset({
    "management", "mgmt", "properties", "property", "realty",
    "group", "llc", "inc", "corp", "associates",
})

_NON_MANAGER_MARKERS = frozenset({
    "section 8", "hcvp", "mtm", "ofs", "renewal", "eviction",
    "notice", "signing", "pays", "payment", "waiting", "lapsed",
    "faith", "hello", "program", "tenant", "owner", "lease",
    "addendum", "making", "possible", "month to month",
    # Report/portfolio aggregate labels — too generic to be manager names.
    # AppFolio metadata and section headers frequently contain these strings.
    "portfolio", "all properties", "all managers", "all units",
    "portfolio wide", "portfolio summary", "combined", "grand total", "subtotal",
})

# Words that commonly prefix a management suffix in a non-person context.
# "All Properties" passes the suffix check ("properties" is a suffix) but the
# first token "all" signals this is a label, not a name.
_NON_NAME_PREFIXES = frozenset({
    "all", "combined", "total", "grand", "full", "complete",
    "any", "each", "every", "other", "various", "misc",
})


def is_manager_tag(tag: str) -> bool:
    """True when a tag string plausibly names a site manager or management company.

    Rejects common AppFolio lease-level tags and report aggregate labels that
    should never create managers.

    Accept rules (checked in order):
    1. Any rejection marker is a substring → False.
    2. Last token is a management suffix AND first token is not a non-name
       prefix (e.g. "all", "total") → True.
    3. Two or more alphabetic tokens AND at least one original token starts
       with an uppercase letter (proper-noun signal) → True.
    """
    lower = tag.strip().lower()
    if not lower:
        return False

    if any(marker in lower for marker in _NON_MANAGER_MARKERS):
        return False

    tokens = lower.split()

    if tokens[-1] in _MANAGER_SUFFIXES:
        # Reject labels like "All Properties", "Combined Group"
        if tokens[0] in _NON_NAME_PREFIXES:
            return False
        return True

    alpha_tokens = [t for t in tokens if t.isalpha() and len(t) > 1]
    if len(alpha_tokens) >= 2:
        # Require at least one proper-noun indicator: an original token that
        # starts with an uppercase letter. This rejects all-lowercase report
        # labels while accepting person names like "Alex Budavich".
        original_tokens = tag.strip().split()
        if any(t and t[0].isupper() and t.isalpha() for t in original_tokens):
            return True

    return False


# ---------------------------------------------------------------------------
# Metadata-based manager + scope extraction
# Deterministic — runs before the LLM touches the document.
# ---------------------------------------------------------------------------

_MANAGER_METADATA_KEYS = ("property_groups", "report_group", "group", "manager")


def resolve_manager_from_metadata(
    metadata: dict[str, str],
) -> tuple[str | None, str]:
    """Extract manager name and scope from parsed document metadata.

    Returns ``(manager_name, scope)`` where manager_name is the raw tag
    string (e.g. "Ryan Steen Mgmt") and scope is ``"manager_portfolio"``
    or ``"portfolio_wide"``.

    Only looks at structured metadata keys that reliably identify a
    manager (``property_groups``, ``report_group``, ``group``, ``manager``).
    Report titles and filenames are never used.
    """
    for key in _MANAGER_METADATA_KEYS:
        val = (metadata.get(key) or "").strip()
        if val and is_manager_tag(val):
            return val, "manager_portfolio"
    return None, "portfolio_wide"


# ---------------------------------------------------------------------------
# Property directory detection
# Used by the seeding service to identify which files to load first
# (property directories establish the manager/property source of truth).
# ---------------------------------------------------------------------------

_PROPERTY_DIRECTORY_COLUMN = frozenset({"property"})
_PROPERTY_DIRECTORY_MANAGER_COLUMNS = frozenset(
    {
        "site manager name",
        "property manager",
        "manager name",
        "assigned manager",
    }
)


def is_property_directory(columns: list[str]) -> bool:
    """True when columns look like an AppFolio property directory report."""
    lower = {c.lower().strip() for c in columns}
    return bool(lower >= _PROPERTY_DIRECTORY_COLUMN and _PROPERTY_DIRECTORY_MANAGER_COLUMNS & lower)


# ---------------------------------------------------------------------------
# Section header detection
# AppFolio rent rolls encode property addresses and occupancy section labels
# as rows with a single non-empty column. The LLM propagates these during
# extraction; this function is available for the rule-based path validation.
# ---------------------------------------------------------------------------

_SECTION_HEADER_VALUES = frozenset(
    {
        "current",
        "vacant",
        "notice",
        "past",
        "future",
        "eviction",
        "month-to-month",
        "total",
        "grand total",
        "subtotal",
        "vacant-unrented",
        "vacant-rented",
        "notice-unrented",
        "notice-rented",
    }
)


def is_section_header(row: dict[str, Any], property_key: str = "property_address") -> bool:
    """True when a row is a section header rather than a data row."""
    prop = str(row.get(property_key) or "").strip().lower()
    if prop in _SECTION_HEADER_VALUES:
        return True
    non_empty = sum(1 for v in row.values() if v is not None and str(v).strip())
    return non_empty <= 1 and not prop


# ---------------------------------------------------------------------------
# Persistable entity types
# ---------------------------------------------------------------------------

PERSISTABLE_TYPES: frozenset[str] = frozenset(
    {
        "Unit",
        "Tenant",
        "Lease",
        "BalanceObservation",
        "Property",
        "MaintenanceRequest",
        "Owner",
        "Vendor",
        "PropertyManager",
    }
)

# ---------------------------------------------------------------------------
# Report type authority — what each report type is allowed to create.
#
# If a report type is absent, unknown, or the entity type is absent from its
# set, the row is BLOCKED and not persisted.  This is the single source of
# truth for write permissions — no authority logic lives in the persisters.
#
# "enrich-only" entity types (Property in rent_roll, Unit in delinquency)
# are intentionally absent: those report types may touch existing records
# but must never create new ones.  The persister functions already guard
# individual enrich paths; this table guards the dispatch decision.
# ---------------------------------------------------------------------------

REPORT_CAN_CREATE: dict[str, frozenset[str]] = {
    "property_directory": frozenset({
        "Property", "PropertyManager", "Unit",
    }),
    "rent_roll": frozenset({
        "Unit", "Lease", "Tenant",
    }),
    "lease_expiration": frozenset({
        "Lease", "Tenant",
    }),
    "delinquency": frozenset({
        "BalanceObservation", "Tenant",
        # Property and Unit intentionally absent — delinquency must not
        # create phantom properties or inflate vacancy counts.
    }),
    "maintenance": frozenset({
        "MaintenanceRequest",
    }),
    "work_order": frozenset({
        "MaintenanceRequest",
    }),
    "tenant_directory": frozenset({
        "Tenant",
    }),
    "owner_directory": frozenset({
        "Owner",
    }),
    "vendor_directory": frozenset({
        "Vendor",
    }),
    "manager_directory": frozenset({
        "PropertyManager",
    }),
}

# ---------------------------------------------------------------------------
# Sentinel dates for leases without explicit bounds
# ---------------------------------------------------------------------------

LEASE_START_FALLBACK = date(2000, 1, 1)
LEASE_END_FALLBACK = date(2099, 12, 31)

# ---------------------------------------------------------------------------
# Enum maps — raw report strings to domain enums
# ---------------------------------------------------------------------------

TENANT_STATUS_MAP: dict[str, TenantStatus] = {
    "current": TenantStatus.CURRENT,
    "notice": TenantStatus.NOTICE,
    "demand": TenantStatus.DEMAND,
    "filing": TenantStatus.FILING,
    "hearing": TenantStatus.HEARING,
    "judgment": TenantStatus.JUDGMENT,
    "evict": TenantStatus.EVICT,
    "eviction": TenantStatus.EVICT,
    "past": TenantStatus.PAST,
}

MAINTENANCE_CATEGORY_MAP: dict[str, TradeCategory] = {
    "plumbing": TradeCategory.PLUMBING,
    "electrical": TradeCategory.ELECTRICAL,
    "hvac": TradeCategory.HVAC,
    "appliance": TradeCategory.APPLIANCE,
    "structural": TradeCategory.STRUCTURAL,
    "general": TradeCategory.GENERAL,
    "cleaning": TradeCategory.CLEANING,
    "painting": TradeCategory.PAINTING,
    "flooring": TradeCategory.FLOORING,
    "roofing": TradeCategory.ROOFING,
    "landscaping": TradeCategory.LANDSCAPING,
    "other": TradeCategory.OTHER,
}

MAINTENANCE_STATUS_MAP: dict[str, MaintenanceStatus] = {
    "open": MaintenanceStatus.OPEN,
    "in_progress": MaintenanceStatus.IN_PROGRESS,
    "in progress": MaintenanceStatus.IN_PROGRESS,
    "completed": MaintenanceStatus.COMPLETED,
    "complete": MaintenanceStatus.COMPLETED,
    "closed": MaintenanceStatus.COMPLETED,
    "cancelled": MaintenanceStatus.CANCELLED,
    "canceled": MaintenanceStatus.CANCELLED,
}

PRIORITY_MAP: dict[str, Priority] = {
    "low": Priority.LOW,
    "medium": Priority.MEDIUM,
    "normal": Priority.MEDIUM,
    "high": Priority.HIGH,
    "urgent": Priority.URGENT,
    "emergency": Priority.EMERGENCY,
}

# ---------------------------------------------------------------------------
# Type coercion — safe on arbitrary user-supplied strings
# ---------------------------------------------------------------------------

_DATE_FORMATS = (
    "%m/%d/%Y",
    "%Y-%m-%d",
    "%m-%d-%Y",
    "%m/%d/%y",
    "%Y/%m/%d",
    "%d-%b-%Y",
    "%b %d, %Y",
)


def to_date(val: object) -> date | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    text = str(val).strip()
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


_CURRENCY_STRIP_RE = re.compile(r"[$,\s]")
_PARENS_RE = re.compile(r"^\((.+)\)$")


def to_decimal(val: object) -> Decimal:
    if val is None:
        return Decimal("0")
    if isinstance(val, bool):
        return Decimal("0")
    if isinstance(val, Decimal):
        return val
    if isinstance(val, (int, float)):
        return Decimal(str(val))
    text = _CURRENCY_STRIP_RE.sub("", str(val).strip())
    if not text:
        return Decimal("0")
    m = _PARENS_RE.match(text)
    if m:
        text = f"-{m.group(1)}"
    try:
        return Decimal(text)
    except InvalidOperation:
        return Decimal("0")


def to_decimal_or_none(val: object) -> Decimal | None:
    """Like to_decimal but returns None when the value is absent/empty,
    so callers can distinguish 'not provided' from '$0'."""
    if val is None:
        return None
    if isinstance(val, bool):
        return None
    if isinstance(val, Decimal):
        return val
    if isinstance(val, (int, float)):
        return Decimal(str(val))
    text = _CURRENCY_STRIP_RE.sub("", str(val).strip())
    if not text:
        return None
    m = _PARENS_RE.match(text)
    if m:
        text = f"-{m.group(1)}"
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def to_int(val: object) -> int | None:
    if val is None:
        return None
    if isinstance(val, int):
        return val
    try:
        return int(float(str(val).strip()))
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Address parsing
# ---------------------------------------------------------------------------

_STREET_SUFFIXES = frozenset(
    {
        "st",
        "ave",
        "avenue",
        "blvd",
        "boulevard",
        "ct",
        "court",
        "dr",
        "drive",
        "ln",
        "lane",
        "pl",
        "place",
        "rd",
        "road",
        "sq",
        "street",
        "ter",
        "terrace",
        "way",
        "cir",
        "circle",
        "pkwy",
        "parkway",
        "hwy",
        "highway",
        "run",
        "alley",
        "aly",
    }
)

_CITY_STATE_ZIP_RE = re.compile(r",\s*([A-Za-z\s]+),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$")
_STATE_ZIP_RE = re.compile(r",\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$")
_TRAILING_STATE_RE = re.compile(r",\s*([A-Z]{2})\s*$")


def _split_address(raw: str) -> tuple[str, str, str, str]:
    addr = raw.strip()
    if not addr:
        return ("", "", "", "")
    m = _CITY_STATE_ZIP_RE.search(addr)
    if m:
        street = addr[: m.start()].strip().rstrip(",")
        return (street, m.group(1).strip(), m.group(2), m.group(3))
    m = _STATE_ZIP_RE.search(addr)
    if m:
        before_comma = addr[: m.start()].strip()
        state = m.group(1)
        zipcode = m.group(2)
        tokens = before_comma.split()
        city_parts: list[str] = []
        for tok in reversed(tokens):
            low = tok.lower().rstrip(".")
            if low in _STREET_SUFFIXES or not tok[0].isupper():
                break
            city_parts.insert(0, tok)
        if city_parts:
            city = " ".join(city_parts)
            street = before_comma[: before_comma.rfind(city_parts[0])].strip()
        else:
            city = ""
            street = before_comma
        return (street, city, state, zipcode)
    m = _TRAILING_STATE_RE.search(addr)
    if m:
        street = addr[: m.start()].strip().rstrip(",")
        return (street, "", m.group(1), "")
    return (addr, "", "", "")


def property_name(address: str) -> str:
    street, _city, _state, _zipcode = _split_address(address)
    return street if street else address.strip()


def parse_address(raw: str) -> Address:
    street, city, state, zipcode = _split_address(raw)
    return Address(street=street or raw.strip(), city=city, state=state, zip_code=zipcode)

