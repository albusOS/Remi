"""API schemas for properties.

Read-model types are owned by the service layer and re-exported here for
use as FastAPI ``response_model`` values.  Only request types and envelope
wrappers (list responses) are defined in this module.
"""

from __future__ import annotations

from pydantic import BaseModel

from remi.domain.intelligence.queries.properties import (
    PropertyDetail,
    PropertyDetailUnit,
    PropertyListItem,
)
from remi.domain.intelligence.queries.rent_roll import (
    LeaseInRentRoll,
    MaintenanceInRentRoll,
    RentRollResult,
    RentRollRow,
    TenantInRentRoll,
)

__all__ = [
    "LeaseInRentRoll",
    "MaintenanceInRentRoll",
    "PropertyDetail",
    "PropertyDetailUnit",
    "PropertyListItem",
    "PropertyListResponse",
    "RentRollResult",
    "RentRollRow",
    "TenantInRentRoll",
    "UnitListResponse",
    "UpdatePropertyRequest",
]


class PropertyListResponse(BaseModel):
    properties: list[PropertyListItem]


class UnitListResponse(BaseModel):
    property_id: str
    count: int
    units: list[PropertyDetailUnit]


class UpdatePropertyRequest(BaseModel):
    name: str | None = None
    street: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    portfolio_id: str | None = None
