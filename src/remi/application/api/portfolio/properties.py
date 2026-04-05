"""REST endpoints for properties and units."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from remi.agent.signals import SignalStore
from remi.application.services.queries import (
    DashboardQueryService,
    PortfolioQueryService,
    RentRollResult,
    RentRollService,
)
from remi.application.api.schemas import (
    PropertyDetail,
    PropertyListResponse,
    UnitListResponse,
    UpdatePropertyRequest,
)
from remi.application.core.models import Address, UnitStatus
from remi.application.core.protocols import PropertyStore
from remi.application.core.events import EventStore
from remi.application.api.dependencies import (
    get_dashboard_service,
    get_event_store,
    get_portfolio_query,
    get_property_store,
    get_rent_roll_service,
    get_signal_store,
)
from remi.application.api.shared_schemas import DeletedResponse, UpdatedResponse
from remi.types.errors import NotFoundError

router = APIRouter(prefix="/properties", tags=["properties"])


@router.get("", response_model=PropertyListResponse)
async def list_properties(
    portfolio_id: str | None = None,
    svc: PortfolioQueryService = Depends(get_portfolio_query),
) -> PropertyListResponse:
    items = await svc.list_properties(portfolio_id=portfolio_id)
    return PropertyListResponse(properties=items)


@router.get("/{property_id}", response_model=PropertyDetail)
async def get_property(
    property_id: str,
    svc: PortfolioQueryService = Depends(get_portfolio_query),
) -> PropertyDetail:
    detail = await svc.get_property_detail(property_id)
    if not detail:
        raise NotFoundError("Property", property_id)
    return detail


@router.get("/{property_id}/units", response_model=UnitListResponse)
async def list_units(
    property_id: str,
    status: str | None = None,
    svc: PortfolioQueryService = Depends(get_portfolio_query),
) -> UnitListResponse:
    detail = await svc.get_property_detail(property_id)
    if not detail:
        raise NotFoundError("Property", property_id)
    units = detail.units
    if status:
        target = UnitStatus(status)
        units = [u for u in units if u.status == target.value]
    return UnitListResponse(
        property_id=property_id,
        count=len(units),
        units=units,
    )


@router.get("/{property_id}/rent-roll", response_model=RentRollResult)
async def rent_roll(
    property_id: str,
    svc: RentRollService = Depends(get_rent_roll_service),
) -> RentRollResult:
    result = await svc.build_rent_roll(property_id)
    if result is None:
        raise NotFoundError("Property", property_id)
    return result


@router.patch("/{property_id}")
async def update_property(
    property_id: str,
    body: UpdatePropertyRequest,
    ps: PropertyStore = Depends(get_property_store),
) -> UpdatedResponse:
    prop = await ps.get_property(property_id)
    if not prop:
        raise NotFoundError("Property", property_id)

    updates: dict[str, object] = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.portfolio_id is not None:
        updates["portfolio_id"] = body.portfolio_id
    if any(f is not None for f in (body.street, body.city, body.state, body.zip_code)):
        updates["address"] = Address(
            street=body.street or prop.address.street,
            city=body.city or prop.address.city,
            state=body.state or prop.address.state,
            zip_code=body.zip_code or prop.address.zip_code,
        )

    updated = prop.model_copy(update=updates)
    await ps.upsert_property(updated)
    return UpdatedResponse(id=property_id, name=updated.name)


@router.get("/{property_id}/context")
async def property_context(
    property_id: str,
    svc: PortfolioQueryService = Depends(get_portfolio_query),
    rent_roll: RentRollService = Depends(get_rent_roll_service),
    dash: DashboardQueryService = Depends(get_dashboard_service),
    signals: SignalStore = Depends(get_signal_store),
    events: EventStore = Depends(get_event_store),
) -> dict[str, Any]:
    """Composite context for a property — one call for the frontend detail page.

    Returns rent roll, active signals, recent changes, vacancies,
    maintenance summary, and expiring leases in a single response.
    """
    import asyncio

    detail = await svc.get_property_detail(property_id)
    if not detail:
        raise NotFoundError("Property", property_id)

    rr_task = rent_roll.build_rent_roll(property_id)
    sig_task = signals.list_signals(scope={"property_id": property_id})
    ev_task = events.list_by_entity(property_id, limit=20)
    maint_task = svc.maintenance_summary(property_id=property_id)

    rr, sigs, changesets, maint = await asyncio.gather(
        rr_task, sig_task, ev_task, maint_task,
    )

    from remi.application.api.intelligence.signal_schemas import SignalSummary

    return {
        "property": detail.model_dump(mode="json"),
        "rent_roll": rr.model_dump(mode="json") if rr else None,
        "signals": [
            SignalSummary(
                signal_id=s.signal_id,
                signal_type=s.signal_type,
                severity=s.severity.value,
                entity_type=s.entity_type,
                entity_id=s.entity_id,
                entity_name=s.entity_name,
                description=s.description,
                detected_at=s.detected_at.isoformat(),
            ).model_dump(mode="json")
            for s in sigs
        ],
        "recent_events": len(changesets),
        "maintenance": maint.model_dump(mode="json"),
    }


@router.delete("/{property_id}", status_code=200)
async def delete_property(
    property_id: str,
    ps: PropertyStore = Depends(get_property_store),
) -> DeletedResponse:
    deleted = await ps.delete_property(property_id)
    if not deleted:
        raise NotFoundError("Property", property_id)
    return DeletedResponse()
