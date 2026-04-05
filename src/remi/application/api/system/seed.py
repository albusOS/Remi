"""Seed endpoints — ingest AppFolio report exports.

POST /api/v1/seed/reports — ingest from an explicit directory
"""

from __future__ import annotations

from pathlib import Path

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from remi.application.services.seeding.service import IngestedReport, SeedResult, SeedService
from remi.application.api.dependencies import get_seed_service
from remi.types.errors import IngestionError

router = APIRouter(prefix="/seed", tags=["seed"])
logger = structlog.get_logger("remi.seed")


class SeedRequest(BaseModel):
    report_dir: str


class SeedResponse(BaseModel):
    ok: bool
    reports_ingested: list[IngestedReport]
    managers_created: int
    properties_created: int
    auto_assigned: int
    errors: list[str]


def _to_response(result: SeedResult) -> SeedResponse:
    return SeedResponse(
        ok=result.ok,
        reports_ingested=result.reports_ingested,
        managers_created=result.managers_created,
        properties_created=result.properties_created,
        auto_assigned=result.auto_assigned,
        errors=result.errors,
    )


@router.post("/reports", response_model=SeedResponse)
async def seed_reports(
    body: SeedRequest,
    seed_service: SeedService = Depends(get_seed_service),
) -> SeedResponse:
    """Ingest AppFolio exports from a directory.

    Report type is detected by the LLM pipeline — filenames don't matter.
    Property directory reports are ingested first. Safe to call multiple times.
    """
    result = await seed_service.seed_from_reports(Path(body.report_dir))
    if not result.ok and not result.reports_ingested:
        raise IngestionError(result.errors[0] if result.errors else "Seed failed")
    return _to_response(result)
