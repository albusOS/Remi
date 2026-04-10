"""Property — a real estate asset."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from remi.application.core.models._helpers import _utcnow
from remi.application.core.models.address import Address
from remi.application.core.models.enums import AssetClass, PropertyStatus, PropertyType


class Property(BaseModel, frozen=True):
    id: str
    manager_id: str | None = None
    name: str
    address: Address
    status: PropertyStatus = PropertyStatus.ACTIVE
    property_type: PropertyType = PropertyType.MULTI_FAMILY
    asset_class: AssetClass | None = None
    year_built: int | None = None
    owner_id: str | None = None
    unit_count: int | None = None
    neighborhood: str | None = None
    year_renovated: int | None = None
    acquisition_date: date | None = None
    management_start_date: date | None = None
    manager_tag: str | None = None
    content_hash: str | None = None
    source_document_id: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
