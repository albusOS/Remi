"""Owner — the legal entity that owns a property asset."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from remi.application.core.models._helpers import _utcnow


class Owner(BaseModel, frozen=True):
    """The legal entity that owns a property asset.

    May be the management company itself (through its development arm),
    an individual investor, an LP, or a trust. Owners are active
    participants in operational decisions — approving payment plans,
    authorizing non-renewals, funding capital improvements.
    """

    id: str
    name: str
    entity_type_label: str = ""
    email: str = ""
    phone: str | None = None
    content_hash: str | None = None
    source_document_id: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
