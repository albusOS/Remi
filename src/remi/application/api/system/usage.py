"""Usage API — LLM cost and token tracking across all call sites."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query

from remi.agent.observe import LLMUsageLedger, UsageReport, UsageSummary
from remi.application.api.dependencies import get_usage_ledger

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("")
async def usage_report(
    hours: int | None = Query(None, description="Filter to last N hours"),
    recent_limit: int = Query(20, ge=1, le=100, description="Number of recent records"),
    ledger: LLMUsageLedger = Depends(get_usage_ledger),
) -> UsageReport:
    since = datetime.now(UTC) - timedelta(hours=hours) if hours else None
    return ledger.report(since=since, recent_limit=recent_limit)


@router.get("/summary")
async def usage_summary(
    hours: int | None = Query(None, description="Filter to last N hours"),
    ledger: LLMUsageLedger = Depends(get_usage_ledger),
) -> UsageSummary:
    since = datetime.now(UTC) - timedelta(hours=hours) if hours else None
    return ledger.summary(since=since)
