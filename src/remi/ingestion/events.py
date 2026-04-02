"""Canonical ingestion event types for the REMI domain.

Emitted by source adapters (AppFolio, etc.) and consumed by the ingestion
engine. These are the canonical vocabulary that decouples adapter format
knowledge from persistence logic.

Structured log event name constants have moved to ``remi.observe.events``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from remi.portfolio.models import (
    Address,
    LeaseStatus,
    OccupancyStatus,
    TenantStatus,
    UnitStatus,
)

# ---------------------------------------------------------------------------
# Ingestion events
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceRef:
    """Tracks which document and platform produced an event."""

    platform: str
    report_type: str
    doc_id: str


@dataclass(frozen=True)
class ScopeReplace:
    """Instructs the engine to delete existing units/leases for a property
    before applying the incoming batch — used for full-replace reports like
    rent rolls and delinquency reports.
    """

    property_id: str
    source: SourceRef
    replace_units: bool = False
    replace_leases: bool = False


@dataclass(frozen=True)
class PropertyObserved:
    property_id: str
    name: str
    address: Address
    source: SourceRef
    portfolio_id: str | None = None


@dataclass(frozen=True)
class ManagerObserved:
    manager_tag: str
    property_id: str
    source: SourceRef


@dataclass(frozen=True)
class UnitObserved:
    unit_id: str
    property_id: str
    unit_number: str
    status: UnitStatus
    source: SourceRef
    occupancy_status: OccupancyStatus | None = None
    bedrooms: int | None = None
    bathrooms: float | None = None
    sqft: int | None = None
    market_rent: Decimal = Decimal("0")
    current_rent: Decimal = Decimal("0")
    days_vacant: int | None = None
    listed_on_website: bool = False
    listed_on_internet: bool = False


@dataclass(frozen=True)
class TenantObserved:
    tenant_id: str
    name: str
    status: TenantStatus
    source: SourceRef
    balance_owed: Decimal = Decimal("0")
    balance_0_30: Decimal = Decimal("0")
    balance_30_plus: Decimal = Decimal("0")
    last_payment_date: date | None = None
    tags: list[str] = field(default_factory=list)
    phone: str | None = None


@dataclass(frozen=True)
class LeaseObserved:
    lease_id: str
    unit_id: str
    tenant_id: str
    property_id: str
    monthly_rent: Decimal
    market_rent: Decimal
    deposit: Decimal
    status: LeaseStatus
    source: SourceRef
    start_date: date | None = None
    end_date: date | None = None
    is_month_to_month: bool = False


IngestionEvent = (
    ScopeReplace
    | PropertyObserved
    | ManagerObserved
    | UnitObserved
    | TenantObserved
    | LeaseObserved
)

__all__ = [
    "IngestionEvent",
    "LeaseObserved",
    "ManagerObserved",
    "PropertyObserved",
    "ScopeReplace",
    "SourceRef",
    "TenantObserved",
    "UnitObserved",
]
