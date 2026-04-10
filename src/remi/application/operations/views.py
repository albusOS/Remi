"""Operations read-model types — leases, maintenance, tenants, delinquency, vacancies."""

from __future__ import annotations

from pydantic import BaseModel


# -- Lease models -------------------------------------------------------------


class LeaseListItem(BaseModel):
    id: str
    tenant_id: str
    tenant: str
    unit_id: str
    property_id: str
    start: str
    end: str
    rent: float
    status: str
    subsidy_program: str | None = None
    notice_days: int | None = None
    is_month_to_month: bool = False
    renewal_status: str | None = None


class LeaseListResult(BaseModel):
    count: int
    leases: list[LeaseListItem]


class LeaseInfo(BaseModel, frozen=True):
    lease_id: str
    unit: str
    property_id: str
    start: str
    end: str
    monthly_rent: float
    status: str


class ExpiringLease(BaseModel):
    lease_id: str
    tenant_name: str
    property_id: str
    property_name: str
    unit_id: str
    unit_number: str
    manager_id: str | None = None
    manager_name: str | None = None
    monthly_rent: float
    market_rent: float
    end_date: str
    days_left: int
    is_month_to_month: bool


class LeaseCalendar(BaseModel):
    days_window: int
    total_expiring: int
    month_to_month_count: int
    leases: list[ExpiringLease]


# -- Maintenance models -------------------------------------------------------


class MaintenanceItem(BaseModel):
    id: str
    property_id: str
    unit_id: str
    title: str
    description: str
    category: str
    priority: str
    status: str
    source: str | None
    vendor: str | None
    cost: float | None
    scheduled_date: str | None
    completed_date: str | None
    created: str
    resolved: str | None


class MaintenanceListResult(BaseModel):
    count: int
    requests: list[MaintenanceItem]


class MaintenanceSummaryResult(BaseModel):
    total: int
    by_status: dict[str, int]
    by_category: dict[str, int]
    total_cost: float


# -- Tenant models ------------------------------------------------------------


class TenantDetail(BaseModel, frozen=True):
    tenant_id: str
    name: str
    email: str | None = None
    phone: str | None = None
    leases: list[LeaseInfo]


# -- Delinquency models -------------------------------------------------------


class DelinquentTenant(BaseModel):
    tenant_id: str
    tenant_name: str
    status: str
    property_id: str | None = None
    property_name: str = ""
    unit_id: str | None = None
    unit_number: str = ""
    manager_id: str | None = None
    manager_name: str | None = None
    balance_owed: float
    balance_0_30: float
    balance_30_plus: float
    last_payment_date: str | None
    delinquency_notes: str | None = None


class DelinquencyBoard(BaseModel):
    total_delinquent: int
    total_balance: float
    tenants: list[DelinquentTenant]


# -- Vacancy models -----------------------------------------------------------


class VacantUnit(BaseModel):
    unit_id: str
    unit_number: str
    property_id: str
    property_name: str
    manager_id: str | None = None
    manager_name: str | None = None
    occupancy_status: str | None
    days_vacant: int | None
    market_rent: float


class VacancyTracker(BaseModel):
    total_vacant: int
    total_notice: int
    total_market_rent_at_risk: float
    avg_days_vacant: float | None
    units: list[VacantUnit]
