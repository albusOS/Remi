"""Seed endpoint — ingest AppFolio report exports in dependency order.

POST /api/v1/seed/reports   — ingest the bundled sample reports
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from remi.types.errors import IngestionError
from remi.domain.ingestion.seeding.service import IngestedReport, SeedService
from remi.shell.api.dependencies import get_seed_service

router = APIRouter(prefix="/seed", tags=["seed"])
logger = structlog.get_logger("remi.seed")


class SeedResponse(BaseModel):
    ok: bool
    reports_ingested: list[IngestedReport]
    managers_created: int
    properties_created: int
    auto_assigned: int
    signals_produced: int
    history_snapshots: int
    errors: list[str]


@router.post("/reports", response_model=SeedResponse)
async def seed_reports(
    seed_service: SeedService = Depends(get_seed_service),
) -> SeedResponse:
    """Ingest the bundled AppFolio sample reports in dependency order.

    Safe to call multiple times — documents and entities are upserted, not
    duplicated. Triggers auto-assign and signal pipeline after ingestion.
    """
    result = await seed_service.seed_from_reports()

    if not result.ok and not result.reports_ingested:
        detail = result.errors[0] if result.errors else "Seed failed"
        raise IngestionError(detail)

    return SeedResponse(
        ok=result.ok,
        reports_ingested=result.reports_ingested,
        managers_created=result.managers_created,
        properties_created=result.properties_created,
        auto_assigned=result.auto_assigned,
        signals_produced=result.signals_produced,
        history_snapshots=result.history_snapshots,
        errors=result.errors,
    )
