"""Type coercion, address parsing, and enum maps for ingestion rows.

Pure leaf module — zero I/O, zero LLM. Imported by persisters, context,
and matcher. Every function is deterministic and safe to call on arbitrary
user-supplied strings.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from remi.application.core.models.address import Address
from remi.application.core.models.enums import (
    MaintenanceStatus,
    Priority,
    TenantStatus,
    TradeCategory,
)

# ---------------------------------------------------------------------------
# Entity types that have ROW_PERSISTERS in persisters.py
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
    """Best-effort date parsing. Returns None on failure."""
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
    """Parse a currency/numeric value into Decimal. Returns 0 on failure."""
    if val is None:
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


def to_int(val: object) -> int | None:
    """Safe integer coercion. Returns None on failure."""
    if val is None:
        return None
    if isinstance(val, int):
        return val
    try:
        return int(float(str(val).strip()))
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Address / property name helpers
# ---------------------------------------------------------------------------

_CITY_STATE_ZIP_RE = re.compile(r",\s*([A-Za-z\s]+),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$")

_TRAILING_STATE_RE = re.compile(r",\s*([A-Z]{2})\s*$")


def property_name(address: str) -> str:
    """Extract the canonical short name from a full address.

    Strips city/state/zip suffix: "123 Main St, Pittsburgh, PA 15203" -> "123 Main St"
    """
    addr = address.strip()
    if not addr:
        return ""
    m = _CITY_STATE_ZIP_RE.search(addr)
    if m:
        return addr[: m.start()].strip().rstrip(",")
    m = _TRAILING_STATE_RE.search(addr)
    if m:
        return addr[: m.start()].strip().rstrip(",")
    return addr


def parse_address(raw: str) -> Address:
    """Split a raw address string into an Address model.

    Handles "123 Main St, Pittsburgh, PA 15203" and partial addresses
    where city/state/zip may be missing.
    """
    raw = raw.strip()
    m = _CITY_STATE_ZIP_RE.search(raw)
    if m:
        street = raw[: m.start()].strip().rstrip(",")
        return Address(
            street=street,
            city=m.group(1).strip(),
            state=m.group(2),
            zip_code=m.group(3),
        )
    parts = [p.strip() for p in raw.split(",")]
    return Address(
        street=parts[0] if parts else raw,
        city=parts[1] if len(parts) > 1 else "",
        state=parts[2].split()[0] if len(parts) > 2 else "",
        zip_code=(parts[2].split()[1] if len(parts) > 2 and len(parts[2].split()) > 1 else ""),
    )
