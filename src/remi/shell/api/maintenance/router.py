"""REST endpoints for maintenance requests."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from remi.domain.queries.maintenance import (
    MaintenanceListResult,
    MaintenanceQueryService,
    MaintenanceSummaryResult,
)
from remi.shell.api.dependencies import get_maintenance_query

router = APIRouter(prefix="/maintenance", tags=["maintenance"])


@router.get("", response_model=MaintenanceListResult)
async def list_requests(
    property_id: str | None = None,
    status: str | None = None,
    svc: MaintenanceQueryService = Depends(get_maintenance_query),
) -> MaintenanceListResult:
    return await svc.list_requests(property_id=property_id, status=status)


@router.get("/summary", response_model=MaintenanceSummaryResult)
async def maintenance_summary(
    property_id: str | None = None,
    svc: MaintenanceQueryService = Depends(get_maintenance_query),
) -> MaintenanceSummaryResult:
    return await svc.maintenance_summary(property_id=property_id)
