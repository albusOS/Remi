"""Tenant — a person or company that occupies a unit."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from remi.application.core.models._helpers import _utcnow
from remi.application.core.models.enums import TenantStatus


class Tenant(BaseModel, frozen=True):
    """Tenant identity and legal/eviction tracking.

    Balance data is NOT stored here — see BalanceObservation.
    """

    id: str
    name: str
    email: str = ""
    phone: str | None = None
    status: TenantStatus = TenantStatus.CURRENT
    content_hash: str | None = None
    source_document_id: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
