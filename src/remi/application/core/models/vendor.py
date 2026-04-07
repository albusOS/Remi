"""Vendor — a contractor or service provider."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from remi.application.core.models._helpers import _utcnow
from remi.application.core.models.enums import TradeCategory


class Vendor(BaseModel, frozen=True):
    """A service provider contracted for maintenance, repairs, or renovations.

    ``is_internal`` distinguishes the firm's own maintenance company from
    outside contractors — critical for performance tracking when the PM
    company is vertically integrated.
    """

    id: str
    name: str
    category: TradeCategory = TradeCategory.GENERAL
    phone: str | None = None
    email: str | None = None
    is_internal: bool = False
    license_number: str | None = None
    insurance_expiry: date | None = None
    rating: float | None = None
    content_hash: str | None = None
    source_document_id: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
