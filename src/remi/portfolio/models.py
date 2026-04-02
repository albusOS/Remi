"""Property management domain models — entity DTOs and enums.

Repository protocols live in ``portfolio.protocols``.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EntityType(StrEnum):
    """Well-known entity types for the REMI real-estate product."""

    PROPERTY_MANAGER = "PropertyManager"
    PROPERTY = "Property"
    PORTFOLIO = "Portfolio"
    UNIT = "Unit"
    TENANT = "Tenant"
    LEASE = "Lease"
    MAINTENANCE_REQUEST = "MaintenanceRequest"


class PropertyType(StrEnum):
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    MIXED = "mixed"
    INDUSTRIAL = "industrial"


class UnitStatus(StrEnum):
    VACANT = "vacant"
    OCCUPIED = "occupied"
    MAINTENANCE = "maintenance"
    OFFLINE = "offline"


class LeaseStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"
    PENDING = "pending"


class MaintenanceCategory(StrEnum):
    PLUMBING = "plumbing"
    ELECTRICAL = "electrical"
    HVAC = "hvac"
    APPLIANCE = "appliance"
    STRUCTURAL = "structural"
    GENERAL = "general"
    OTHER = "other"


class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EMERGENCY = "emergency"


class MaintenanceStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class OccupancyStatus(StrEnum):
    OCCUPIED = "occupied"
    NOTICE_RENTED = "notice_rented"
    NOTICE_UNRENTED = "notice_unrented"
    VACANT_RENTED = "vacant_rented"
    VACANT_UNRENTED = "vacant_unrented"


class TenantStatus(StrEnum):
    CURRENT = "current"
    NOTICE = "notice"
    EVICT = "evict"


class ActionItemStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class ActionItemPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Address(BaseModel, frozen=True):
    street: str
    city: str
    state: str
    zip_code: str
    country: str = "US"

    def one_line(self) -> str:
        return f"{self.street}, {self.city}, {self.state} {self.zip_code}"


class PropertyManager(BaseModel, frozen=True):
    id: str
    name: str
    email: str = ""
    company: str | None = None
    phone: str | None = None
    manager_tag: str | None = None
    portfolio_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utcnow)


class Portfolio(BaseModel, frozen=True):
    id: str
    manager_id: str
    name: str
    description: str = ""
    property_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utcnow)


class Property(BaseModel, frozen=True):
    id: str
    portfolio_id: str
    name: str
    address: Address
    property_type: PropertyType = PropertyType.RESIDENTIAL
    year_built: int | None = None
    source_document_id: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class Unit(BaseModel, frozen=True):
    id: str
    property_id: str
    unit_number: str
    bedrooms: int | None = None
    bathrooms: float | None = None
    sqft: int | None = None
    market_rent: Decimal = Decimal("0")
    current_rent: Decimal = Decimal("0")
    status: UnitStatus = UnitStatus.VACANT
    occupancy_status: OccupancyStatus | None = None
    days_vacant: int | None = None
    listed_on_website: bool = False
    listed_on_internet: bool = False
    floor: int | None = None
    source_document_id: str | None = None


class Lease(BaseModel, frozen=True):
    id: str
    unit_id: str
    tenant_id: str
    property_id: str
    start_date: date
    end_date: date
    monthly_rent: Decimal
    deposit: Decimal = Decimal("0")
    status: LeaseStatus = LeaseStatus.ACTIVE
    market_rent: Decimal = Decimal("0")
    is_month_to_month: bool = False
    source_document_id: str | None = None


class Tenant(BaseModel, frozen=True):
    id: str
    name: str
    email: str = ""
    phone: str | None = None
    status: TenantStatus = TenantStatus.CURRENT
    balance_owed: Decimal = Decimal("0")
    balance_0_30: Decimal = Decimal("0")
    balance_30_plus: Decimal = Decimal("0")
    last_payment_date: date | None = None
    tags: list[str] = Field(default_factory=list)
    lease_ids: list[str] = Field(default_factory=list)
    source_document_id: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)


class MaintenanceRequest(BaseModel, frozen=True):
    id: str
    unit_id: str
    property_id: str
    tenant_id: str | None = None
    category: MaintenanceCategory = MaintenanceCategory.GENERAL
    priority: Priority = Priority.MEDIUM
    title: str = ""
    description: str = ""
    status: MaintenanceStatus = MaintenanceStatus.OPEN
    created_at: datetime = Field(default_factory=_utcnow)
    resolved_at: datetime | None = None
    cost: Decimal | None = None
    vendor: str | None = None


class ActionItem(BaseModel, frozen=True):
    """User-created action item tied to a manager, property, or tenant."""

    id: str
    title: str
    description: str = ""
    status: ActionItemStatus = ActionItemStatus.OPEN
    priority: ActionItemPriority = ActionItemPriority.MEDIUM
    manager_id: str | None = None
    property_id: str | None = None
    tenant_id: str | None = None
    due_date: date | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


