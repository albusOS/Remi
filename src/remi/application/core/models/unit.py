"""Unit — a rentable space within a property.

Physical facts only. Occupancy, current rent, and balance are derived at
query time from Lease and BalanceObservation records.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from remi.application.core.models._helpers import _utcnow
from remi.application.core.models.enums import OccupancyStatus, UnitType


class Unit(BaseModel, frozen=True):
    """Physical facts about a unit — never derived from report data.

    market_rent is the CURRENT assessed market rate for this unit, updated
    when new rent comp data or pricing tools provide it.

    occupancy_status and days_vacant are set by the ingestion pipeline from
    rent roll / vacancy reports when a full Lease record cannot be created
    (e.g. the report has lease dates but no tenant name). They serve as a
    fallback when the Lease store has no matching record for this unit.
    """

    id: str
    property_id: str
    unit_number: str
    bedrooms: int | None = None
    bathrooms: float | None = None
    sqft: int | None = None
    unit_type: UnitType | None = None
    floor: int | None = None
    market_rent: Decimal = Decimal("0")
    occupancy_status: OccupancyStatus | None = None
    days_vacant: int | None = None
    content_hash: str | None = None
    source_document_id: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
