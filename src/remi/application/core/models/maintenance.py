"""Maintenance — work orders for units."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from remi.application.core.models._helpers import _utcnow
from remi.application.core.models.enums import (
    MaintenanceSource,
    MaintenanceStatus,
    Priority,
    TradeCategory,
)


class MaintenanceRequest(BaseModel, frozen=True):
    """A maintenance work order.

    ``completed_date`` is the actual work-completion date recorded in the
    source report (e.g. AppFolio "Completed On") — distinct from
    ``resolved_at`` which is the system timestamp when we last marked the
    record as resolved. For analytics ("trends over the past year"),
    filter on ``completed_date``.
    """

    id: str
    unit_id: str
    property_id: str
    tenant_id: str | None = None
    category: TradeCategory = TradeCategory.GENERAL
    priority: Priority = Priority.MEDIUM
    source: MaintenanceSource | None = None
    title: str = ""
    description: str = ""
    status: MaintenanceStatus = MaintenanceStatus.OPEN
    vendor_id: str | None = None
    vendor: str | None = None  # freeform vendor name when vendor_id not resolved
    scheduled_date: date | None = None
    completed_date: date | None = None
    sla_hours: int | None = None
    cost: Decimal | None = None
    content_hash: str | None = None
    source_document_id: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    resolved_at: datetime | None = None
