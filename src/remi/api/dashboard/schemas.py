"""Dashboard API response schemas.

Re-exports from the service module — the service owns the canonical models.
"""

from __future__ import annotations

from pydantic import BaseModel

from remi.models.rollups import ManagerSnapshot, PropertySnapshot
from remi.services.dashboard import (
    DelinquencyBoard,
    DelinquentTenant,
    ExpiringLease,
    LeaseCalendar,
    ManagerOverview,
    PortfolioOverview,
    RentRollUnit,
    RentRollView,
    VacancyTracker,
    VacantUnit,
)

__all__ = [
    "AutoAssignResponse",
    "CaptureResponse",
    "DelinquencyBoard",
    "DelinquentTenant",
    "ExpiringLease",
    "LeaseCalendar",
    "ManagerOverview",
    "MetricsHistoryResponse",
    "NeedsManagerResponse",
    "PortfolioOverview",
    "RentRollUnit",
    "RentRollView",
    "SnapshotsResponse",
    "UnassignedProperty",
    "VacancyTracker",
    "VacantUnit",
]


class UnassignedProperty(BaseModel, frozen=True):
    id: str
    name: str
    address: str


class NeedsManagerResponse(BaseModel, frozen=True):
    total: int
    properties: list[UnassignedProperty]


class SnapshotsResponse(BaseModel, frozen=True):
    total: int
    snapshots: list[ManagerSnapshot]


class CaptureResponse(BaseModel, frozen=True):
    captured: int


class MetricsHistoryResponse(BaseModel, frozen=True):
    entity_type: str
    total: int
    snapshots: list[ManagerSnapshot | PropertySnapshot]


class AutoAssignResponse(BaseModel, frozen=True):
    assigned: int
    unresolved: int
    message: str
