"""Dashboard REST endpoints — pure PropertyStore aggregation views."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from remi.application.api.intelligence.dashboard_schemas import (
    AutoAssignResponse,
    NeedsManagerResponse,
    UnassignedProperty,
)
from remi.application.services.queries import (
    AutoAssignService,
    DashboardQueryService,
    DelinquencyBoard,
    LeaseCalendar,
    PortfolioOverview,
    RentRollView,
    VacancyTracker,
)
from remi.application.core.protocols import PropertyStore
from remi.application.api.dependencies import (
    get_auto_assign_service,
    get_dashboard_service,
    get_property_store,
)
from remi.types.errors import NotFoundError

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


@router.post("/auto-assign", response_model=AutoAssignResponse)
async def auto_assign(
    svc: AutoAssignService = Depends(get_auto_assign_service),
) -> AutoAssignResponse:
    result = await svc.auto_assign()
    return AutoAssignResponse(
        assigned=result.assigned,
        unresolved=result.unresolved,
        tags_available=result.tags_available,
        message=result.message,
    )
