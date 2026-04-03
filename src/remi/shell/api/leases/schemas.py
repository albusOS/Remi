"""API schemas for leases.

Read-model types are owned by the service layer and re-exported here.
Only request types and envelope wrappers are defined in this module.
"""

from __future__ import annotations

from pydantic import BaseModel

from remi.domain.intelligence.queries.leases import ExpiringLeaseItem

__all__ = [
    "ExpiringLeaseItem",
    "ExpiringLeasesResponse",
    "LeaseListItem",
    "LeaseListResponse",
]


class LeaseListItem(BaseModel):
    id: str
    tenant: str
    unit_id: str
    property_id: str
    start: str
    end: str
    rent: float
    status: str


class LeaseListResponse(BaseModel):
    count: int
    leases: list[LeaseListItem]


class ExpiringLeasesResponse(BaseModel):
    days_window: int
    count: int
    leases: list[ExpiringLeaseItem]
