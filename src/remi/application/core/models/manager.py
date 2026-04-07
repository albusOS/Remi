"""Manager — a property manager responsible for a portfolio."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from remi.application.core.models._helpers import _utcnow


class PropertyManager(BaseModel, frozen=True):
    id: str
    name: str
    email: str = ""
    company: str | None = None
    phone: str | None = None
    manager_tag: str | None = None
    title: str | None = None
    territory: str | None = None
    max_units: int | None = None
    license_number: str | None = None
    content_hash: str | None = None
    source_document_id: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
