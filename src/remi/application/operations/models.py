"""Operations read-model types — leases, maintenance, tenants."""

from __future__ import annotations

from pydantic import BaseModel


class LeaseListItem(BaseModel):
    id: str
    tenant: str
    unit_id: str
    property_id: str
    start: str
    end: str
    rent: float
    status: str


class LeaseListResult(BaseModel):
    count: int
    leases: list[LeaseListItem]


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


class LeaseInfo(BaseModel, frozen=True):
    lease_id: str
    unit: str
    property_id: str
    start: str
    end: str
    monthly_rent: float
    status: str


class TenantDetail(BaseModel, frozen=True):
    tenant_id: str
    name: str
    email: str | None = None
    phone: str | None = None
    leases: list[LeaseInfo]
