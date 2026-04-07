"""REST endpoints for cross-property unit queries."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter

from remi.application.api.schemas import (
    CreateUnitRequest,
    CreateUnitResponse,
    UpdateUnitRequest,
)
from remi.application.api.shared_schemas import DeletedResponse, UpdatedResponse
from remi.application.core.models import Unit
from remi.application.views import UnitListResult
from remi.shell.api.dependencies import Ctr
from remi.types.errors import NotFoundError
from remi.types.identity import unit_id as _unit_id

router = APIRouter(prefix="/units", tags=["units"])


@router.get("", response_model=UnitListResult)
async def list_all_units(
    c: Ctr,
    property_id: str | None = None,
) -> UnitListResult:
    return await c.property_resolver.list_all_units(property_id=property_id)


@router.post("", response_model=CreateUnitResponse, status_code=201)
async def create_unit(
    body: CreateUnitRequest,
    c: Ctr,
) -> CreateUnitResponse:
    prop = await c.property_store.get_property(body.property_id)
    if not prop:
        raise NotFoundError("Property", body.property_id)

    uid = _unit_id(body.property_id, body.unit_number)
    unit = Unit(
        id=uid,
        property_id=body.property_id,
        unit_number=body.unit_number,
        bedrooms=body.bedrooms,
        bathrooms=body.bathrooms,
        sqft=body.sqft,
        market_rent=Decimal(str(body.market_rent)),
        floor=body.floor,
    )
    await c.property_store.upsert_unit(unit)
    return CreateUnitResponse(
        unit_id=uid,
        property_id=body.property_id,
        unit_number=body.unit_number,
    )


@router.patch("/{unit_id}")
async def update_unit(
    unit_id: str,
    body: UpdateUnitRequest,
    c: Ctr,
) -> UpdatedResponse:
    unit = await c.property_store.get_unit(unit_id)
    if not unit:
        raise NotFoundError("Unit", unit_id)

    updates: dict[str, object] = {}
    if body.unit_number is not None:
        updates["unit_number"] = body.unit_number
    if body.bedrooms is not None:
        updates["bedrooms"] = body.bedrooms
    if body.bathrooms is not None:
        updates["bathrooms"] = body.bathrooms
    if body.sqft is not None:
        updates["sqft"] = body.sqft
    if body.market_rent is not None:
        updates["market_rent"] = Decimal(str(body.market_rent))
    if body.floor is not None:
        updates["floor"] = body.floor

    updated = unit.model_copy(update=updates)
    await c.property_store.upsert_unit(updated)
    return UpdatedResponse(id=unit_id, name=updated.unit_number)


@router.delete("/{unit_id}", status_code=200)
async def delete_unit(
    unit_id: str,
    c: Ctr,
) -> DeletedResponse:
    deleted = await c.property_store.delete_unit(unit_id)
    if not deleted:
        raise NotFoundError("Unit", unit_id)
    return DeletedResponse()
