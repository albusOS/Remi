"""Dashboard API response schemas.

Re-exports from the service module — the service owns the canonical models.
"""

from __future__ import annotations

from pydantic import BaseModel

from remi.application.services.queries import (  # noqa: F401
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
    "DelinquencyBoard",
    "DelinquentTenant",
    "ExpiringLease",
    "LeaseCalendar",
    "ManagerOverview",
    "NeedsManagerResponse",
    "PortfolioOverview",
    "RentRollUnit",
    "RentRollView",
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


class AutoAssignResponse(BaseModel, frozen=True):
    assigned: int
    unresolved: int
    tags_available: int
    message: str
