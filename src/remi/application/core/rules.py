"""Pure business rule functions for portfolio entities.

Stateless, no I/O — just computations over domain objects.

Occupancy rules derive state from Lease records; Unit no longer carries
status or current_rent fields. Every service that needs to classify a unit
(dashboard, manager_review, rent_roll) should use these functions so the
rules stay consistent across views.
"""

from __future__ import annotations

import re as _re
import unicodedata as _unicodedata
from decimal import Decimal

from remi.application.core.models import (
    Lease,
    LeaseStatus,
    MaintenanceRequest,
    MaintenanceStatus,
    OccupancyStatus,
)

BELOW_MARKET_THRESHOLD = 0.03  # 3 % gap between current and market rent


def active_lease(leases: list[Lease]) -> Lease | None:
    """Return the currently active lease for a unit, or None if vacant."""
    return next((le for le in leases if le.status == LeaseStatus.ACTIVE), None)


def is_occupied(leases: list[Lease]) -> bool:
    """True when the unit has an active lease."""
    return active_lease(leases) is not None


def is_vacant(leases: list[Lease]) -> bool:
    """True when the unit has no active lease."""
    return active_lease(leases) is None


def derive_occupancy_status(leases: list[Lease]) -> OccupancyStatus:
    """Derive the rich occupancy status from a unit's lease history."""
    act = active_lease(leases)
    has_pending = any(le.status == LeaseStatus.PENDING for le in leases)
    if act:
        if act.notice_date:
            return OccupancyStatus.NOTICE_RENTED if has_pending else OccupancyStatus.NOTICE_UNRENTED
        return OccupancyStatus.OCCUPIED
    return OccupancyStatus.VACANT_RENTED if has_pending else OccupancyStatus.VACANT_UNRENTED


def current_rent(leases: list[Lease]) -> Decimal:
    """Return the current monthly rent from the active lease, or zero."""
    act = active_lease(leases)
    return act.monthly_rent if act else Decimal("0")


def loss_to_lease(market_rent: Decimal, lease_rent: Decimal) -> Decimal:
    """Per-unit loss-to-lease (zero when current >= market or unit is vacant)."""
    if lease_rent > 0 and lease_rent < market_rent:
        return market_rent - lease_rent
    return Decimal("0")


def is_below_market(market_rent: Decimal, lease_rent: Decimal) -> bool:
    """True when the unit's rent gap exceeds the threshold."""
    if market_rent <= 0:
        return False
    if lease_rent >= market_rent:
        return False
    return float((market_rent - lease_rent) / market_rent) > BELOW_MARKET_THRESHOLD


def pct_below_market(market_rent: Decimal, lease_rent: Decimal) -> float:
    """Percentage the unit is below market (0.0 when at or above)."""
    if market_rent <= 0 or lease_rent >= market_rent:
        return 0.0
    return round(float((market_rent - lease_rent) / market_rent) * 100, 1)


def is_maintenance_open(request: MaintenanceRequest) -> bool:
    """True when a maintenance request should count as open/active."""
    return request.status in (MaintenanceStatus.OPEN, MaintenanceStatus.IN_PROGRESS)


_LEGAL_SUFFIXES = frozenset(
    {
        "llc",
        "llp",
        "lp",
        "inc",
        "corp",
        "co",
        "ltd",
        "plc",
        "management",
        "mgmt",
        "managing",
        "property",
        "properties",
        "portfolio",
        "portfolios",
        "group",
        "groups",
        "realty",
        "real",
        "estate",
        "associates",
        "services",
        "solutions",
        "partners",
        "partnership",
        "agency",
        "enterprises",
        "holdings",
    }
)
_HONORIFICS = frozenset({"mr", "mrs", "ms", "dr", "prof"})
_PUNCT_RE = _re.compile(r"[.,/#!$%^&*;:{}=\-_`~()'\"]+")


def normalize_entity_name(raw: str) -> str:
    """Canonical form of any person or organization name.

    Strips legal suffixes (LLC, Mgmt, Properties, etc.), honorifics,
    punctuation, and extra whitespace. Returns a space-separated
    lowercase token string suitable for slug generation and similarity
    comparison.

    Examples:
      "Ryan Steen Property Management LLC" → "ryan steen"
      "R. Steen Mgmt."                     → "r steen"
      "Dr. Jake Kraus"                     → "jake kraus"
    """
    normalized = _unicodedata.normalize("NFKD", raw)
    ascii_str = normalized.encode("ascii", "ignore").decode("ascii")
    lower = _PUNCT_RE.sub(" ", ascii_str.lower())
    tokens = lower.split()

    while tokens and tokens[0] in _HONORIFICS:
        tokens.pop(0)

    changed = True
    while changed and tokens:
        changed = False
        if tokens[-1] in _LEGAL_SUFFIXES:
            tokens.pop()
            changed = True

    while tokens and tokens[0] in _LEGAL_SUFFIXES:
        tokens.pop(0)

    result = " ".join(tokens).strip()
    return result if result else " ".join(raw.split()).lower()


def manager_name_from_tag(tag: str) -> str:
    """Extract and normalize the person's name from a manager tag.

    Returns a display-friendly title-cased name with legal suffixes stripped.
    Uses normalize_entity_name for suffix removal, then title-cases the result
    so "ryan steen property management llc" → "Ryan Steen".
    """
    return normalize_entity_name(tag).title()
