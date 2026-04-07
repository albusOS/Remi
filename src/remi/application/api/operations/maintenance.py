"""REST endpoints for maintenance requests."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter

from remi.application.api.schemas import (
    CreateMaintenanceRequest,
    CreateMaintenanceResponse,
    UpdateMaintenanceRequest,
)
from remi.application.api.shared_schemas import DeletedResponse, UpdatedResponse
from remi.application.core.models import (
    MaintenanceRequest,
    MaintenanceStatus,
    Priority,
    TradeCategory,
)
from remi.application.views import (
    MaintenanceListResult,
    MaintenanceSummaryResult,
)
from remi.shell.api.dependencies import Ctr
from remi.types.errors import NotFoundError
from remi.types.identity import maintenance_id as _maintenance_id

router = APIRouter(prefix="/maintenance", tags=["maintenance"])


@router.get("", response_model=MaintenanceListResult)
async def list_requests(
    c: Ctr,
    property_id: str | None = None,
    unit_id: str | None = None,
    manager_id: str | None = None,
    status: str | None = None,
) -> MaintenanceListResult:
    return await c.maintenance_resolver.list_maintenance(
        property_id=property_id,
        unit_id=unit_id,
        manager_id=manager_id,
        status=status,
    )


@router.get("/summary", response_model=MaintenanceSummaryResult)
async def maintenance_summary(
    c: Ctr,
    property_id: str | None = None,
    unit_id: str | None = None,
    manager_id: str | None = None,
) -> MaintenanceSummaryResult:
    return await c.maintenance_resolver.maintenance_summary(
        property_id=property_id,
        unit_id=unit_id,
        manager_id=manager_id,
    )


@router.post("", response_model=CreateMaintenanceResponse, status_code=201)
async def create_maintenance(
    body: CreateMaintenanceRequest,
    c: Ctr,
) -> CreateMaintenanceResponse:
    prop = await c.property_store.get_property(body.property_id)
    if not prop:
        raise NotFoundError("Property", body.property_id)
    unit = await c.property_store.get_unit(body.unit_id)
    if not unit:
        raise NotFoundError("Unit", body.unit_id)

    request_id = _maintenance_id(body.property_id, body.unit_id, body.title)
    req = MaintenanceRequest(
        id=request_id,
        unit_id=body.unit_id,
        property_id=body.property_id,
        title=body.title,
        description=body.description,
        category=TradeCategory(body.category),
        priority=Priority(body.priority),
    )
    await c.property_store.upsert_maintenance_request(req)
    return CreateMaintenanceResponse(
        request_id=request_id,
        title=body.title,
        property_id=body.property_id,
        unit_id=body.unit_id,
    )


@router.patch("/{request_id}")
async def update_maintenance(
    request_id: str,
    body: UpdateMaintenanceRequest,
    c: Ctr,
) -> UpdatedResponse:
    req = await c.property_store.get_maintenance_request(request_id)
    if not req:
        raise NotFoundError("MaintenanceRequest", request_id)

    updates: dict[str, object] = {}
    if body.title is not None:
        updates["title"] = body.title
    if body.description is not None:
        updates["description"] = body.description
    if body.status is not None:
        updates["status"] = MaintenanceStatus(body.status)
    if body.priority is not None:
        updates["priority"] = Priority(body.priority)
    if body.category is not None:
        updates["category"] = TradeCategory(body.category)
    if body.vendor is not None:
        updates["vendor"] = body.vendor
    if body.cost is not None:
        updates["cost"] = Decimal(str(body.cost))

    updated = req.model_copy(update=updates)
    await c.property_store.upsert_maintenance_request(updated)
    return UpdatedResponse(id=request_id, name=updated.title)


@router.delete("/{request_id}", status_code=200)
async def delete_maintenance(
    request_id: str,
    c: Ctr,
) -> DeletedResponse:
    deleted = await c.property_store.delete_maintenance_request(request_id)
    if not deleted:
        raise NotFoundError("MaintenanceRequest", request_id)
    return DeletedResponse()
