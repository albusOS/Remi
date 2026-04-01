"""Dashboard REST endpoints — pure PropertyStore aggregation views."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from remi.api.dashboard.schemas import (
    AutoAssignResponse,
    CaptureResponse,
    MetricsHistoryResponse,
    NeedsManagerResponse,
    SnapshotsResponse,
    UnassignedProperty,
)
from remi.api.dependencies import (
    get_auto_assign_service,
    get_dashboard_service,
    get_property_store,
    get_snapshot_service,
)
from remi.models.properties import PropertyStore
from remi.services.auto_assign import AutoAssignService
from remi.services.dashboard import (
    DashboardQueryService,
    DelinquencyBoard,
    LeaseCalendar,
    PortfolioOverview,
    RentRollView,
    VacancyTracker,
)
from remi.services.snapshots import SnapshotService
from remi.shared.errors import NotFoundError

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=PortfolioOverview)
async def overview(
    manager_id: str | None = None,
    svc: DashboardQueryService = Depends(get_dashboard_service),
) -> PortfolioOverview:
    return await svc.portfolio_overview(manager_id=manager_id)


@router.get("/delinquency", response_model=DelinquencyBoard)
async def delinquency(
    manager_id: str | None = None,
    svc: DashboardQueryService = Depends(get_dashboard_service),
) -> DelinquencyBoard:
    return await svc.delinquency_board(manager_id=manager_id)


@router.get("/leases/expiring", response_model=LeaseCalendar)
async def leases_expiring(
    days: int = 90,
    manager_id: str | None = None,
    svc: DashboardQueryService = Depends(get_dashboard_service),
) -> LeaseCalendar:
    return await svc.lease_expiration_calendar(days=days, manager_id=manager_id)


@router.get("/rent-roll/{property_id}", response_model=RentRollView)
async def rent_roll(
    property_id: str,
    svc: DashboardQueryService = Depends(get_dashboard_service),
) -> RentRollView:
    result = await svc.rent_roll(property_id)
    if result is None:
        raise NotFoundError("Property", property_id)
    return result


@router.get("/vacancies", response_model=VacancyTracker)
async def vacancies(
    manager_id: str | None = None,
    svc: DashboardQueryService = Depends(get_dashboard_service),
) -> VacancyTracker:
    return await svc.vacancy_tracker(manager_id=manager_id)


@router.get("/needs-manager", response_model=NeedsManagerResponse)
async def needs_manager(
    ps: PropertyStore = Depends(get_property_store),
) -> NeedsManagerResponse:
    all_props = await ps.list_properties()
    items = [
        UnassignedProperty(id=p.id, name=p.name, address=p.address.one_line())
        for p in all_props
        if not p.portfolio_id
    ]
    return NeedsManagerResponse(total=len(items), properties=items)


@router.get("/snapshots", response_model=SnapshotsResponse)
async def snapshots(
    manager_id: str | None = Query(default=None),
    snap: SnapshotService = Depends(get_snapshot_service),
) -> SnapshotsResponse:
    history = await snap.get_history(manager_id=manager_id)
    return SnapshotsResponse(total=len(history), snapshots=history)


@router.post("/snapshots/capture", response_model=CaptureResponse)
async def capture_snapshot(
    snap: SnapshotService = Depends(get_snapshot_service),
) -> CaptureResponse:
    batch = await snap.capture()
    return CaptureResponse(captured=len(batch))


@router.get("/metrics-history", response_model=MetricsHistoryResponse)
async def metrics_history(
    entity_type: str = Query(default="manager", description="'manager' or 'property'"),
    entity_id: str | None = Query(
        default=None,
        description="Filter to a specific manager_id or property_id",
    ),
    manager_id: str | None = Query(
        default=None,
        description="Filter property snapshots by manager",
    ),
    days: int = Query(default=90, ge=1, le=3650, description="Look back this many days"),
    snap: SnapshotService = Depends(get_snapshot_service),
) -> MetricsHistoryResponse:
    from datetime import UTC, datetime, timedelta

    since = datetime.now(UTC) - timedelta(days=days)

    if entity_type == "property":
        rows = await snap.get_property_history(
            property_id=entity_id,
            manager_id=manager_id,
            since=since,
        )
    else:
        rows = await snap.get_history(manager_id=entity_id, since=since)

    return MetricsHistoryResponse(
        entity_type=entity_type,
        total=len(rows),
        snapshots=rows,
    )


@router.post("/auto-assign", response_model=AutoAssignResponse)
async def auto_assign(
    svc: AutoAssignService = Depends(get_auto_assign_service),
) -> AutoAssignResponse:
    result = await svc.auto_assign()
    return AutoAssignResponse(
        assigned=result.assigned,
        unresolved=result.unresolved,
        message=result.message,
    )
