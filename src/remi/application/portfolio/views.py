"""Portfolio read-model types — managers, properties, units, rent-roll, dashboard."""

from __future__ import annotations

from pydantic import BaseModel

from remi.application.core.models import Address


# -- Property models ----------------------------------------------------------


class PropertyListItem(BaseModel):
    id: str
    name: str
    address: str
    type: str
    year_built: int | None
    total_units: int
    occupied: int
    manager_id: str | None = None
    owner_id: str | None = None
    owner_name: str | None = None


class PropertyDetailUnit(BaseModel):
    id: str
    property_id: str
    unit_number: str
    status: str  # derived: "occupied" | "vacant"
    is_vacant: bool = False
    occupancy_status: str | None = None
    bedrooms: int | None
    bathrooms: float | None
    sqft: int | None
    floor: int | None
    market_rent: float
    current_rent: float


class PropertyDetail(BaseModel):
    id: str
    name: str
    address: Address
    property_type: str
    year_built: int | None
    manager_id: str | None = None
    manager_name: str | None = None
    owner_id: str | None = None
    owner_name: str | None = None
    total_units: int
    occupied: int
    vacant: int
    occupancy_rate: float
    monthly_revenue: float
    active_leases: int
    units: list[PropertyDetailUnit]


# -- Unit models --------------------------------------------------------------


class UnitListItem(BaseModel):
    id: str
    unit_number: str
    property_name: str
    property_id: str
    status: str
    is_vacant: bool = False
    bedrooms: int | None = None
    sqft: int | None = None
    market_rent: float
    current_rent: float


class UnitListResult(BaseModel):
    count: int
    units: list[UnitListItem]


# -- Rent-roll models ---------------------------------------------------------


class LeaseInRentRoll(BaseModel):
    id: str
    status: str
    start_date: str
    end_date: str
    monthly_rent: float
    deposit: float
    days_to_expiry: int | None


class TenantInRentRoll(BaseModel):
    id: str
    name: str
    email: str
    phone: str | None


class MaintenanceInRentRoll(BaseModel):
    id: str
    title: str
    category: str
    priority: str
    status: str
    cost: float | None


class RentRollRow(BaseModel):
    unit_id: str
    unit_number: str
    floor: int | None
    bedrooms: int | None
    bathrooms: float | None
    sqft: int | None
    status: str
    market_rent: float
    current_rent: float
    rent_gap: float
    pct_below_market: float
    lease: LeaseInRentRoll | None
    tenant: TenantInRentRoll | None
    open_maintenance: int
    maintenance_items: list[MaintenanceInRentRoll]
    issues: list[str]


class RentRollResult(BaseModel):
    property_id: str
    property_name: str
    total_units: int
    occupied: int
    vacant: int
    total_market_rent: float
    total_actual_rent: float
    total_loss_to_lease: float
    total_vacancy_loss: float
    rows: list[RentRollRow]


# -- Data coverage models -----------------------------------------------------


class DataCoverage(BaseModel):
    """How complete and trustworthy a manager's data is.

    Inferred entirely from what's actually in the graph — no document store
    needed. The agent should include the ``caveat`` in any response that cites
    occupancy rates, revenue, or delinquency for this manager.

    Confidence levels:
      full    — rent roll + leases + delinquency. All key metrics are reliable.
      partial — leases or delinquency present but no rent roll. Occupancy may
                be understated; unit-level physical data is sparse.
      sparse  — only property directory. Unit counts are declared, not verified.
                Most metrics are estimates.
    """

    has_rent_roll: bool
    has_lease_data: bool
    has_delinquency_data: bool
    has_maintenance_data: bool
    unit_record_coverage: float       # records / declared (0.0 – 1.0)
    units_with_physical_data: float   # % of records with beds/baths
    units_with_market_rent: float     # % of records with market_rent > 0
    confidence: str                   # "sparse" | "partial" | "full"
    missing_report_types: list[str]
    caveat: str


# -- Manager review models ----------------------------------------------------


class PropertySummary(BaseModel):
    property_id: str
    property_name: str
    total_units: int
    occupied: int
    vacant: int
    occupancy_rate: float
    monthly_actual: float
    monthly_market: float
    loss_to_lease: float
    vacancy_loss: float
    open_maintenance: int
    emergency_maintenance: int
    expiring_leases: int
    expired_leases: int
    below_market_units: int
    issue_count: int


class UnitIssue(BaseModel):
    property_id: str
    property_name: str
    unit_id: str
    unit_number: str
    issues: list[str]
    monthly_impact: float


class ManagerMetrics(BaseModel, frozen=True):
    """Shared portfolio metrics embedded in every manager view."""

    total_units: int
    occupied: int
    vacant: int
    occupancy_rate: float
    total_actual_rent: float
    total_market_rent: float
    loss_to_lease: float
    vacancy_loss: float
    open_maintenance: int
    expiring_leases_90d: int


class ManagerSummary(BaseModel):
    """Full review with property breakdown and issues."""

    manager_id: str
    name: str
    email: str
    company: str | None
    property_count: int
    metrics: ManagerMetrics
    data_coverage: DataCoverage
    delinquent_count: int
    total_delinquent_balance: float
    expired_leases: int
    below_market_units: int
    emergency_maintenance: int
    properties: list[PropertySummary]
    top_issues: list[UnitIssue]


class ManagerRanking(BaseModel, frozen=True):
    """Ranking table row."""

    manager_id: str
    name: str
    property_count: int
    metrics: ManagerMetrics
    delinquent_count: int
    total_delinquent_balance: float
    delinquency_rate: float


# -- Dashboard models ---------------------------------------------------------


class ManagerOverview(BaseModel):
    """Dashboard card."""

    manager_id: str
    manager_name: str
    property_count: int
    metrics: ManagerMetrics


class PropertyOverview(BaseModel):
    """Per-property row in the dashboard grid."""

    property_id: str
    property_name: str
    address: str
    manager_id: str | None = None
    manager_name: str | None = None
    total_units: int
    occupied: int
    vacant: int
    occupancy_rate: float
    monthly_rent: float
    market_rent: float
    loss_to_lease: float
    open_maintenance: int


class DashboardOverview(BaseModel):
    total_properties: int
    total_units: int
    occupied: int
    vacant: int
    occupancy_rate: float
    total_monthly_rent: float
    total_market_rent: float
    total_loss_to_lease: float
    properties: list[PropertyOverview]
    total_managers: int = 0
    managers: list[ManagerOverview] = []


# -- Assignment models --------------------------------------------------------


class UnassignedProperty(BaseModel, frozen=True):
    id: str
    name: str
    address: str


class NeedsManagerResult(BaseModel, frozen=True):
    total: int
    properties: list[UnassignedProperty]


class AutoAssignResult(BaseModel, frozen=True):
    assigned: int
    unresolved: int
    tags_available: int
    message: str
