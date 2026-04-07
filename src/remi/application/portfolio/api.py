"""Portfolio REST routes — managers, properties, units, owners."""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from decimal import Decimal
from typing import Any

import structlog
from fastapi import APIRouter, Query
from pydantic import BaseModel

from remi.application.core.models import (
    ActionItemStatus,
    Address,
    MeetingBrief,
    Property,
    PropertyManager,
    PropertyType,
    Unit,
)
from remi.application.dependencies import Ctr
from remi.types.errors import ConflictError, DomainError, NotFoundError
from remi.types.identity import (
    manager_id as _manager_id,
    property_id as _property_id,
    unit_id as _unit_id,
)

from .models import (
    ManagerRanking,
    ManagerSummary,
    PropertyDetail,
    PropertyDetailUnit,
    PropertyListItem,
    RentRollResult,
    UnitListResult,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["portfolio"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class DeletedResponse(BaseModel, frozen=True):
    deleted: bool = True


class UpdatedResponse(BaseModel, frozen=True):
    id: str
    name: str


class ManagerListResponse(BaseModel):
    managers: list[ManagerSummary]


class ManagerRankingsResponse(BaseModel):
    rankings: list[ManagerRanking]
    total: int
    sort_by: str


class CreateManagerRequest(BaseModel):
    name: str
    email: str = ""
    company: str | None = None
    phone: str | None = None


class CreateManagerResponse(BaseModel):
    manager_id: str
    name: str


class UpdateManagerRequest(BaseModel):
    name: str | None = None
    email: str | None = None
    company: str | None = None
    phone: str | None = None


class MergeManagersRequest(BaseModel):
    source_manager_id: str
    target_manager_id: str


class MergeManagersResponse(BaseModel):
    target_manager_id: str
    properties_moved: int
    source_deleted: bool


class AssignPropertiesRequest(BaseModel):
    property_ids: list[str]


class AssignPropertiesResponse(BaseModel):
    manager_id: str
    assigned: int
    already_assigned: int
    not_found: list[str]


class PropertyListResponse(BaseModel):
    properties: list[PropertyListItem]


class UnitListResponse(BaseModel):
    property_id: str
    count: int
    units: list[PropertyDetailUnit]


class CreatePropertyRequest(BaseModel):
    name: str
    manager_id: str | None = None
    owner_id: str | None = None
    street: str
    city: str
    state: str
    zip_code: str
    property_type: str = "multi_family"
    year_built: int | None = None


class CreatePropertyResponse(BaseModel):
    property_id: str
    name: str


class UpdatePropertyRequest(BaseModel):
    name: str | None = None
    street: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    manager_id: str | None = None
    owner_id: str | None = None


class CreateUnitRequest(BaseModel):
    property_id: str
    unit_number: str
    bedrooms: int | None = None
    bathrooms: float | None = None
    sqft: int | None = None
    market_rent: float = 0
    floor: int | None = None


class CreateUnitResponse(BaseModel):
    unit_id: str
    property_id: str
    unit_number: str


class UpdateUnitRequest(BaseModel):
    unit_number: str | None = None
    bedrooms: int | None = None
    bathrooms: float | None = None
    sqft: int | None = None
    market_rent: float | None = None
    floor: int | None = None


class OwnerListItem(BaseModel):
    id: str
    name: str
    owner_type: str
    company: str | None
    email: str
    phone: str | None
    property_count: int


class MeetingBriefRequest(BaseModel):
    focus: str | None = None


# ---------------------------------------------------------------------------
# Manager routes
# ---------------------------------------------------------------------------

managers_router = APIRouter(prefix="/managers", tags=["managers"])


@managers_router.get("", response_model=ManagerListResponse)
async def list_managers(c: Ctr) -> ManagerListResponse:
    summaries = await c.manager_resolver.list_manager_summaries()
    return ManagerListResponse(managers=summaries)


@managers_router.get("/rankings", response_model=ManagerRankingsResponse)
async def manager_rankings(
    c: Ctr,
    sort_by: str = Query(default="delinquency_rate", description="Field to sort by"),
    ascending: bool = Query(default=False, description="Sort ascending"),
    limit: int | None = Query(default=None, ge=1, description="Max results"),
) -> ManagerRankingsResponse:
    rows = await c.manager_resolver.rank_managers(
        sort_by=sort_by, ascending=ascending, limit=limit,
    )
    return ManagerRankingsResponse(rankings=rows, total=len(rows), sort_by=sort_by)


@managers_router.get("/{manager_id}/review", response_model=ManagerSummary)
async def manager_review(manager_id: str, c: Ctr) -> ManagerSummary:
    result = await c.manager_resolver.aggregate_manager(manager_id)
    if not result:
        raise NotFoundError("Manager", manager_id)
    return result


def _snapshot_hash(pipeline_input: str) -> str:
    return hashlib.sha256(pipeline_input.encode()).hexdigest()[:16]


def _brief_response(brief: MeetingBrief) -> dict[str, Any]:
    return {
        "id": brief.id,
        "manager_id": brief.manager_id,
        "snapshot_hash": brief.snapshot_hash,
        "brief": brief.brief,
        "analysis": brief.analysis,
        "focus": brief.focus,
        "generated_at": brief.generated_at.isoformat(),
        "usage": {
            "prompt_tokens": brief.prompt_tokens,
            "completion_tokens": brief.completion_tokens,
        },
    }


async def _build_pipeline_input(
    c: Ctr, manager_id: str, review: ManagerSummary, focus: str | None,
) -> str:
    delinquency, leases, vacancies, action_items, notes = await asyncio.gather(
        c.dashboard_resolver.delinquency_board(manager_id=manager_id),
        c.dashboard_resolver.lease_expiration_calendar(days=90, manager_id=manager_id),
        c.dashboard_resolver.vacancy_tracker(manager_id=manager_id),
        c.property_store.list_action_items(manager_id=manager_id, status=ActionItemStatus.OPEN),
        c.property_store.list_notes(entity_type="PropertyManager", entity_id=manager_id),
    )
    recent_notes = sorted(notes, key=lambda n: n.created_at, reverse=True)[:10]
    return json.dumps(
        {
            "manager": {"name": review.name, "email": review.email, "company": review.company},
            "metrics": {
                **review.metrics.model_dump(mode="json"),
                "emergency_maintenance": review.emergency_maintenance,
                "expired_leases": review.expired_leases,
                "below_market_units": review.below_market_units,
                "delinquent_count": review.delinquent_count,
                "total_delinquent_balance": review.total_delinquent_balance,
            },
            "properties": [p.model_dump(mode="json") for p in review.properties],
            "delinquency": delinquency.model_dump(mode="json"),
            "leases": leases.model_dump(mode="json"),
            "vacancies": vacancies.model_dump(mode="json"),
            "existing_actions": [
                {"title": a.title, "status": a.status.value, "priority": a.priority.value}
                for a in action_items
            ],
            "notes": [
                {"content": n.content, "created_at": n.created_at.isoformat()}
                for n in recent_notes
            ],
            "focus": focus,
        },
        default=str,
    )


@managers_router.post("/{manager_id}/meeting-brief")
async def generate_meeting_brief(
    manager_id: str, c: Ctr, body: MeetingBriefRequest | None = None,
) -> dict[str, Any]:
    review = await c.manager_resolver.aggregate_manager(manager_id)
    if not review:
        raise NotFoundError("Manager", manager_id)
    focus = body.focus if body else None
    pipeline_input = await _build_pipeline_input(c, manager_id, review, focus)
    snap_hash = _snapshot_hash(pipeline_input)
    logger.info("meeting_brief_start", manager_id=manager_id, snapshot_hash=snap_hash, input_length=len(pipeline_input))
    from remi.agent.workflow import load_workflow
    workflow_def = load_workflow("manager_review")
    result = await c.workflow_runner.run(workflow_def, pipeline_input)
    analysis = result.step("analyze")
    brief_data = result.step("brief")
    if not brief_data or not isinstance(brief_data, dict):
        logger.warning("meeting_brief_empty", manager_id=manager_id, analysis_type=type(analysis).__name__, brief_type=type(brief_data).__name__)
        raise DomainError("Failed to generate meeting brief — LLM returned empty result")
    brief = MeetingBrief(
        id=f"brief:{uuid.uuid4().hex[:12]}",
        manager_id=manager_id,
        snapshot_hash=snap_hash,
        brief=brief_data,
        analysis=analysis if isinstance(analysis, dict) else {},
        focus=focus,
        prompt_tokens=result.total_usage.prompt_tokens,
        completion_tokens=result.total_usage.completion_tokens,
    )
    await c.property_store.upsert_meeting_brief(brief)
    logger.info("meeting_brief_persisted", brief_id=brief.id, manager_id=manager_id, snapshot_hash=snap_hash)
    return _brief_response(brief)


@managers_router.get("/{manager_id}/meeting-briefs")
async def list_meeting_briefs(
    manager_id: str, c: Ctr, limit: int = Query(default=10, ge=1, le=50),
) -> dict[str, Any]:
    mgr = await c.property_store.get_manager(manager_id)
    if not mgr:
        raise NotFoundError("Manager", manager_id)
    briefs = await c.property_store.list_meeting_briefs(manager_id=manager_id, limit=limit)
    review = await c.manager_resolver.aggregate_manager(manager_id)
    current_hash: str | None = None
    if review:
        pipeline_input = await _build_pipeline_input(c, manager_id, review, focus=None)
        current_hash = _snapshot_hash(pipeline_input)
    return {"briefs": [_brief_response(b) for b in briefs], "total": len(briefs), "current_snapshot_hash": current_hash}


@managers_router.post("", response_model=CreateManagerResponse, status_code=201)
async def create_manager(body: CreateManagerRequest, c: Ctr) -> CreateManagerResponse:
    mid = _manager_id(body.name)
    existing = await c.property_store.get_manager(mid)
    if existing:
        raise ConflictError(f"Manager '{body.name}' already exists (id={mid})")
    await c.property_store.upsert_manager(PropertyManager(id=mid, name=body.name, email=body.email, company=body.company, phone=body.phone))
    return CreateManagerResponse(manager_id=mid, name=body.name)


@managers_router.patch("/{manager_id}", response_model=CreateManagerResponse)
async def update_manager(manager_id: str, body: UpdateManagerRequest, c: Ctr) -> CreateManagerResponse:
    mgr = await c.property_store.get_manager(manager_id)
    if not mgr:
        raise NotFoundError("Manager", manager_id)
    updates: dict[str, str | None] = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.email is not None:
        updates["email"] = body.email
    if body.company is not None:
        updates["company"] = body.company
    if body.phone is not None:
        updates["phone"] = body.phone
    updated = mgr.model_copy(update=updates)
    await c.property_store.upsert_manager(updated)
    return CreateManagerResponse(manager_id=manager_id, name=updated.name)


@managers_router.delete("/{manager_id}", status_code=200)
async def delete_manager(manager_id: str, c: Ctr) -> DeletedResponse:
    deleted = await c.property_store.delete_manager(manager_id)
    if not deleted:
        raise NotFoundError("Manager", manager_id)
    return DeletedResponse()


@managers_router.post("/merge", response_model=MergeManagersResponse)
async def merge_managers(body: MergeManagersRequest, c: Ctr) -> MergeManagersResponse:
    ps = c.property_store
    source = await ps.get_manager(body.source_manager_id)
    target = await ps.get_manager(body.target_manager_id)
    if not source:
        raise NotFoundError("Manager", body.source_manager_id)
    if not target:
        raise NotFoundError("Manager", body.target_manager_id)
    source_props = await ps.list_properties(manager_id=body.source_manager_id)
    moved = 0
    for prop in source_props:
        updated = prop.model_copy(update={"manager_id": body.target_manager_id})
        await ps.upsert_property(updated)
        moved += 1
    deleted = await ps.delete_manager(body.source_manager_id)
    return MergeManagersResponse(target_manager_id=body.target_manager_id, properties_moved=moved, source_deleted=deleted)


@managers_router.get("/{manager_id}/context")
async def manager_context(manager_id: str, c: Ctr) -> dict[str, Any]:
    summary_task = c.manager_resolver.aggregate_manager(manager_id)
    ev_task = c.event_store.list_recent(limit=20)
    summary, changesets = await asyncio.gather(summary_task, ev_task)
    if summary is None:
        raise NotFoundError("Manager", manager_id)
    return {"manager": summary.model_dump(mode="json"), "recent_events": len(changesets)}


@managers_router.post("/{manager_id}/assign", response_model=AssignPropertiesResponse)
async def assign_properties(manager_id: str, body: AssignPropertiesRequest, c: Ctr) -> AssignPropertiesResponse:
    ps = c.property_store
    mgr = await ps.get_manager(manager_id)
    if not mgr:
        raise NotFoundError("Manager", manager_id)
    assigned = 0
    already = 0
    not_found: list[str] = []
    for pid in body.property_ids:
        prop = await ps.get_property(pid)
        if not prop:
            not_found.append(pid)
            continue
        if prop.manager_id == manager_id:
            already += 1
            continue
        updated = prop.model_copy(update={"manager_id": manager_id})
        await ps.upsert_property(updated)
        assigned += 1
    return AssignPropertiesResponse(manager_id=manager_id, assigned=assigned, already_assigned=already, not_found=not_found)


# ---------------------------------------------------------------------------
# Property routes
# ---------------------------------------------------------------------------

properties_router = APIRouter(prefix="/properties", tags=["properties"])


@properties_router.get("", response_model=PropertyListResponse)
async def list_properties(c: Ctr, manager_id: str | None = None, owner_id: str | None = None) -> PropertyListResponse:
    items = await c.property_resolver.list_properties(manager_id=manager_id, owner_id=owner_id)
    return PropertyListResponse(properties=items)


@properties_router.post("", response_model=CreatePropertyResponse, status_code=201)
async def create_property(body: CreatePropertyRequest, c: Ctr) -> CreatePropertyResponse:
    pid = _property_id(body.name)
    prop = Property(id=pid, manager_id=body.manager_id, owner_id=body.owner_id, name=body.name, address=Address(street=body.street, city=body.city, state=body.state, zip_code=body.zip_code), property_type=PropertyType(body.property_type), year_built=body.year_built)
    await c.property_store.upsert_property(prop)
    return CreatePropertyResponse(property_id=pid, name=body.name)


@properties_router.get("/{property_id}", response_model=PropertyDetail)
async def get_property(property_id: str, c: Ctr) -> PropertyDetail:
    detail = await c.property_resolver.get_property_detail(property_id)
    if not detail:
        raise NotFoundError("Property", property_id)
    return detail


@properties_router.get("/{property_id}/units", response_model=UnitListResponse)
async def list_units(property_id: str, c: Ctr, status: str | None = None) -> UnitListResponse:
    detail = await c.property_resolver.get_property_detail(property_id)
    if not detail:
        raise NotFoundError("Property", property_id)
    units = detail.units
    if status:
        units = [u for u in units if u.status == status]
    return UnitListResponse(property_id=property_id, count=len(units), units=units)


@properties_router.get("/{property_id}/rent-roll", response_model=RentRollResult)
async def rent_roll(property_id: str, c: Ctr) -> RentRollResult:
    result = await c.rent_roll_resolver.build_rent_roll(property_id)
    if result is None:
        raise NotFoundError("Property", property_id)
    return result


@properties_router.patch("/{property_id}")
async def update_property(property_id: str, body: UpdatePropertyRequest, c: Ctr) -> UpdatedResponse:
    prop = await c.property_store.get_property(property_id)
    if not prop:
        raise NotFoundError("Property", property_id)
    updates: dict[str, object] = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.manager_id is not None:
        updates["manager_id"] = body.manager_id or None
    if body.owner_id is not None:
        updates["owner_id"] = body.owner_id or None
    if any(f is not None for f in (body.street, body.city, body.state, body.zip_code)):
        updates["address"] = Address(street=body.street or prop.address.street, city=body.city or prop.address.city, state=body.state or prop.address.state, zip_code=body.zip_code or prop.address.zip_code)
    updated = prop.model_copy(update=updates)
    await c.property_store.upsert_property(updated)
    return UpdatedResponse(id=property_id, name=updated.name)


@properties_router.get("/{property_id}/context")
async def property_context(property_id: str, c: Ctr) -> dict[str, Any]:
    detail = await c.property_resolver.get_property_detail(property_id)
    if not detail:
        raise NotFoundError("Property", property_id)
    rr_task = c.rent_roll_resolver.build_rent_roll(property_id)
    ev_task = c.event_store.list_by_entity(property_id, limit=20)
    maint_task = c.maintenance_resolver.maintenance_summary(property_id=property_id)
    rr, changesets, maint = await asyncio.gather(rr_task, ev_task, maint_task)
    return {"property": detail.model_dump(mode="json"), "rent_roll": rr.model_dump(mode="json") if rr else None, "recent_events": len(changesets), "maintenance": maint.model_dump(mode="json")}


@properties_router.delete("/{property_id}", status_code=200)
async def delete_property(property_id: str, c: Ctr) -> DeletedResponse:
    deleted = await c.property_store.delete_property(property_id)
    if not deleted:
        raise NotFoundError("Property", property_id)
    return DeletedResponse()


# ---------------------------------------------------------------------------
# Unit routes
# ---------------------------------------------------------------------------

units_router = APIRouter(prefix="/units", tags=["units"])


@units_router.get("", response_model=UnitListResult)
async def list_all_units(c: Ctr, property_id: str | None = None) -> UnitListResult:
    return await c.property_resolver.list_all_units(property_id=property_id)


@units_router.post("", response_model=CreateUnitResponse, status_code=201)
async def create_unit(body: CreateUnitRequest, c: Ctr) -> CreateUnitResponse:
    prop = await c.property_store.get_property(body.property_id)
    if not prop:
        raise NotFoundError("Property", body.property_id)
    uid = _unit_id(body.property_id, body.unit_number)
    unit = Unit(id=uid, property_id=body.property_id, unit_number=body.unit_number, bedrooms=body.bedrooms, bathrooms=body.bathrooms, sqft=body.sqft, market_rent=Decimal(str(body.market_rent)), floor=body.floor)
    await c.property_store.upsert_unit(unit)
    return CreateUnitResponse(unit_id=uid, property_id=body.property_id, unit_number=body.unit_number)


@units_router.patch("/{unit_id}")
async def update_unit(unit_id: str, body: UpdateUnitRequest, c: Ctr) -> UpdatedResponse:
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


@units_router.delete("/{unit_id}", status_code=200)
async def delete_unit(unit_id: str, c: Ctr) -> DeletedResponse:
    deleted = await c.property_store.delete_unit(unit_id)
    if not deleted:
        raise NotFoundError("Unit", unit_id)
    return DeletedResponse()


# ---------------------------------------------------------------------------
# Owner routes
# ---------------------------------------------------------------------------

owners_router = APIRouter(prefix="/owners", tags=["portfolio"])


@owners_router.get("", response_model=list[OwnerListItem])
async def list_owners(c: Ctr) -> list[OwnerListItem]:
    owners = await c.property_store.list_owners()
    all_props = await c.property_store.list_properties()
    props_by_owner: dict[str, int] = {}
    for p in all_props:
        if p.owner_id:
            props_by_owner[p.owner_id] = props_by_owner.get(p.owner_id, 0) + 1
    return [
        OwnerListItem(id=o.id, name=o.name, owner_type=o.owner_type.value, company=o.company, email=o.email, phone=o.phone, property_count=props_by_owner.get(o.id, 0))
        for o in owners
    ]
