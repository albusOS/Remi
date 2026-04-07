"""Operations REST routes — leases, maintenance, tenants, actions, notes."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from remi.application.core.models import (
    ActionItem,
    ActionItemStatus,
    Lease,
    LeaseStatus,
    MaintenanceRequest,
    MaintenanceStatus,
    Note,
    NoteProvenance,
    Priority,
    RenewalStatus,
    Tenant,
    TenantStatus,
    TradeCategory,
)
from remi.application.operations.models import (
    LeaseListResult,
    MaintenanceListResult,
    MaintenanceSummaryResult,
    TenantDetail,
)
from remi.application.portfolio.models import LeaseCalendar
from remi.application.dependencies import Ctr
from remi.types.errors import NotFoundError
from remi.types.identity import (
    lease_id as _lease_id,
    maintenance_id as _maintenance_id,
    tenant_id as _tenant_id,
)

router = APIRouter(tags=["operations"])


# ---------------------------------------------------------------------------
# Shared response models
# ---------------------------------------------------------------------------


class DeletedResponse(BaseModel, frozen=True):
    deleted: bool = True


class UpdatedResponse(BaseModel, frozen=True):
    id: str
    name: str


# ---------------------------------------------------------------------------
# Lease schemas + routes
# ---------------------------------------------------------------------------


class CreateLeaseRequest(BaseModel):
    unit_id: str
    tenant_id: str
    property_id: str
    start_date: str
    end_date: str
    monthly_rent: float
    deposit: float = 0
    status: str = "active"


class CreateLeaseResponse(BaseModel):
    lease_id: str
    unit_id: str
    tenant_id: str
    property_id: str


class UpdateLeaseRequest(BaseModel):
    monthly_rent: float | None = None
    status: str | None = None
    end_date: str | None = None
    renewal_status: str | None = None
    is_month_to_month: bool | None = None


leases_router = APIRouter(prefix="/leases", tags=["leases"])


@leases_router.get("", response_model=LeaseListResult)
async def list_leases(c: Ctr, property_id: str | None = None, status: str | None = None) -> LeaseListResult:
    return await c.lease_resolver.list_leases(property_id=property_id, status=status)


@leases_router.get("/expiring", response_model=LeaseCalendar)
async def expiring_leases(c: Ctr, days: int = 60) -> LeaseCalendar:
    return await c.lease_resolver.expiring_leases(days=days)


@leases_router.post("", response_model=CreateLeaseResponse, status_code=201)
async def create_lease(body: CreateLeaseRequest, c: Ctr) -> CreateLeaseResponse:
    unit = await c.property_store.get_unit(body.unit_id)
    if not unit:
        raise NotFoundError("Unit", body.unit_id)
    tenant = await c.property_store.get_tenant(body.tenant_id)
    if not tenant:
        raise NotFoundError("Tenant", body.tenant_id)
    lid = _lease_id(tenant.name, body.property_id, unit.unit_number)
    lease = Lease(id=lid, unit_id=body.unit_id, tenant_id=body.tenant_id, property_id=body.property_id, start_date=date.fromisoformat(body.start_date), end_date=date.fromisoformat(body.end_date), monthly_rent=Decimal(str(body.monthly_rent)), deposit=Decimal(str(body.deposit)), status=LeaseStatus(body.status))
    await c.property_store.upsert_lease(lease)
    return CreateLeaseResponse(lease_id=lid, unit_id=body.unit_id, tenant_id=body.tenant_id, property_id=body.property_id)


@leases_router.patch("/{lease_id}")
async def update_lease(lease_id: str, body: UpdateLeaseRequest, c: Ctr) -> UpdatedResponse:
    lease = await c.property_store.get_lease(lease_id)
    if not lease:
        raise NotFoundError("Lease", lease_id)
    updates: dict[str, object] = {}
    if body.monthly_rent is not None:
        updates["monthly_rent"] = Decimal(str(body.monthly_rent))
    if body.status is not None:
        updates["status"] = LeaseStatus(body.status)
    if body.end_date is not None:
        updates["end_date"] = date.fromisoformat(body.end_date)
    if body.renewal_status is not None:
        updates["renewal_status"] = RenewalStatus(body.renewal_status)
    if body.is_month_to_month is not None:
        updates["is_month_to_month"] = body.is_month_to_month
    updated = lease.model_copy(update=updates)
    await c.property_store.upsert_lease(updated)
    return UpdatedResponse(id=lease_id, name=f"Lease {lease_id}")


@leases_router.delete("/{lease_id}", status_code=200)
async def delete_lease(lease_id: str, c: Ctr) -> DeletedResponse:
    deleted = await c.property_store.delete_lease(lease_id)
    if not deleted:
        raise NotFoundError("Lease", lease_id)
    return DeletedResponse()


# ---------------------------------------------------------------------------
# Maintenance schemas + routes
# ---------------------------------------------------------------------------


class CreateMaintenanceRequest_(BaseModel):
    unit_id: str
    property_id: str
    title: str
    description: str = ""
    category: str = "general"
    priority: str = "medium"


class CreateMaintenanceResponse(BaseModel):
    request_id: str
    title: str
    property_id: str
    unit_id: str


class UpdateMaintenanceRequest_(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    category: str | None = None
    vendor: str | None = None
    cost: float | None = None


maintenance_router = APIRouter(prefix="/maintenance", tags=["maintenance"])


@maintenance_router.get("", response_model=MaintenanceListResult)
async def list_requests(c: Ctr, property_id: str | None = None, unit_id: str | None = None, manager_id: str | None = None, status: str | None = None) -> MaintenanceListResult:
    return await c.maintenance_resolver.list_maintenance(property_id=property_id, unit_id=unit_id, manager_id=manager_id, status=status)


@maintenance_router.get("/summary", response_model=MaintenanceSummaryResult)
async def maintenance_summary(c: Ctr, property_id: str | None = None, unit_id: str | None = None, manager_id: str | None = None) -> MaintenanceSummaryResult:
    return await c.maintenance_resolver.maintenance_summary(property_id=property_id, unit_id=unit_id, manager_id=manager_id)


@maintenance_router.post("", response_model=CreateMaintenanceResponse, status_code=201)
async def create_maintenance(body: CreateMaintenanceRequest_, c: Ctr) -> CreateMaintenanceResponse:
    prop = await c.property_store.get_property(body.property_id)
    if not prop:
        raise NotFoundError("Property", body.property_id)
    unit = await c.property_store.get_unit(body.unit_id)
    if not unit:
        raise NotFoundError("Unit", body.unit_id)
    request_id = _maintenance_id(body.property_id, body.unit_id, body.title)
    req = MaintenanceRequest(id=request_id, unit_id=body.unit_id, property_id=body.property_id, title=body.title, description=body.description, category=TradeCategory(body.category), priority=Priority(body.priority))
    await c.property_store.upsert_maintenance_request(req)
    return CreateMaintenanceResponse(request_id=request_id, title=body.title, property_id=body.property_id, unit_id=body.unit_id)


@maintenance_router.patch("/{request_id}")
async def update_maintenance(request_id: str, body: UpdateMaintenanceRequest_, c: Ctr) -> UpdatedResponse:
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


@maintenance_router.delete("/{request_id}", status_code=200)
async def delete_maintenance(request_id: str, c: Ctr) -> DeletedResponse:
    deleted = await c.property_store.delete_maintenance_request(request_id)
    if not deleted:
        raise NotFoundError("MaintenanceRequest", request_id)
    return DeletedResponse()


# ---------------------------------------------------------------------------
# Tenant schemas + routes
# ---------------------------------------------------------------------------


class CreateTenantRequest(BaseModel):
    name: str
    property_id: str
    email: str = ""
    phone: str | None = None


class CreateTenantResponse(BaseModel):
    tenant_id: str
    name: str


class UpdateTenantRequest(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    status: str | None = None


tenants_router = APIRouter(prefix="/tenants", tags=["tenants"])


@tenants_router.get("/{tenant_id}", response_model=TenantDetail)
async def get_tenant(tenant_id: str, c: Ctr) -> TenantDetail:
    detail = await c.lease_resolver.tenant_detail(tenant_id)
    if not detail:
        raise NotFoundError("Tenant", tenant_id)
    return detail


@tenants_router.post("", response_model=CreateTenantResponse, status_code=201)
async def create_tenant(body: CreateTenantRequest, c: Ctr) -> CreateTenantResponse:
    tid = _tenant_id(body.name, body.property_id)
    tenant = Tenant(id=tid, name=body.name, email=body.email, phone=body.phone)
    await c.property_store.upsert_tenant(tenant)
    return CreateTenantResponse(tenant_id=tid, name=body.name)


@tenants_router.patch("/{tenant_id}")
async def update_tenant(tenant_id: str, body: UpdateTenantRequest, c: Ctr) -> UpdatedResponse:
    tenant = await c.property_store.get_tenant(tenant_id)
    if not tenant:
        raise NotFoundError("Tenant", tenant_id)
    updates: dict[str, object] = {}
    if body.name is not None:
        updates["name"] = body.name
    if body.email is not None:
        updates["email"] = body.email
    if body.phone is not None:
        updates["phone"] = body.phone
    if body.status is not None:
        updates["status"] = TenantStatus(body.status)
    updated = tenant.model_copy(update=updates)
    await c.property_store.upsert_tenant(updated)
    return UpdatedResponse(id=tenant_id, name=updated.name)


@tenants_router.delete("/{tenant_id}", status_code=200)
async def delete_tenant(tenant_id: str, c: Ctr) -> DeletedResponse:
    deleted = await c.property_store.delete_tenant(tenant_id)
    if not deleted:
        raise NotFoundError("Tenant", tenant_id)
    return DeletedResponse()


# ---------------------------------------------------------------------------
# Action item schemas + routes
# ---------------------------------------------------------------------------


class ActionItemCreate(BaseModel):
    title: str
    description: str = ""
    priority: str = "medium"
    manager_id: str | None = None
    property_id: str | None = None
    tenant_id: str | None = None
    due_date: date | None = None


class ActionItemUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    due_date: date | None = None


class ActionItemResponse(BaseModel):
    id: str
    title: str
    description: str
    status: str
    priority: str
    manager_id: str | None
    property_id: str | None
    tenant_id: str | None
    due_date: str | None
    created_at: str
    updated_at: str


class ActionItemListResponse(BaseModel):
    items: list[ActionItemResponse]
    total: int


def _ai_resp(item: ActionItem) -> ActionItemResponse:
    return ActionItemResponse(id=item.id, title=item.title, description=item.description, status=item.status.value, priority=item.priority.value, manager_id=item.manager_id, property_id=item.property_id, tenant_id=item.tenant_id, due_date=item.due_date.isoformat() if item.due_date else None, created_at=item.created_at.isoformat(), updated_at=item.updated_at.isoformat())


actions_router = APIRouter(prefix="/actions", tags=["actions"])


@actions_router.get("/items", response_model=ActionItemListResponse)
async def list_action_items(c: Ctr, manager_id: str | None = None, property_id: str | None = None, tenant_id: str | None = None, status: str | None = None) -> ActionItemListResponse:
    ai_status = ActionItemStatus(status) if status else None
    items = await c.property_store.list_action_items(manager_id=manager_id, property_id=property_id, tenant_id=tenant_id, status=ai_status)
    items.sort(key=lambda i: i.created_at, reverse=True)
    return ActionItemListResponse(items=[_ai_resp(i) for i in items], total=len(items))


@actions_router.post("/items", response_model=ActionItemResponse, status_code=201)
async def create_action_item(body: ActionItemCreate, c: Ctr) -> ActionItemResponse:
    item = ActionItem(id=f"action:{uuid.uuid4().hex[:12]}", title=body.title, description=body.description, priority=Priority(body.priority), manager_id=body.manager_id, property_id=body.property_id, tenant_id=body.tenant_id, due_date=body.due_date)
    await c.property_store.upsert_action_item(item)
    return _ai_resp(item)


@actions_router.patch("/items/{item_id}", response_model=ActionItemResponse)
async def update_action_item(item_id: str, body: ActionItemUpdate, c: Ctr) -> ActionItemResponse:
    existing = await c.property_store.get_action_item(item_id)
    if not existing:
        raise NotFoundError("ActionItem", item_id)
    updates: dict[str, object] = {"updated_at": datetime.now(UTC)}
    if body.title is not None:
        updates["title"] = body.title
    if body.description is not None:
        updates["description"] = body.description
    if body.status is not None:
        updates["status"] = ActionItemStatus(body.status)
    if body.priority is not None:
        updates["priority"] = Priority(body.priority)
    if body.due_date is not None:
        updates["due_date"] = body.due_date
    updated = existing.model_copy(update=updates)
    await c.property_store.upsert_action_item(updated)
    return _ai_resp(updated)


@actions_router.delete("/items/{item_id}", status_code=200)
async def delete_action_item(item_id: str, c: Ctr) -> DeletedResponse:
    deleted = await c.property_store.delete_action_item(item_id)
    if not deleted:
        raise NotFoundError("ActionItem", item_id)
    return DeletedResponse()


# ---------------------------------------------------------------------------
# Note schemas + routes
# ---------------------------------------------------------------------------


class NoteCreateRequest(BaseModel):
    content: str
    entity_type: str
    entity_id: str
    provenance: NoteProvenance = NoteProvenance.USER_STATED
    source_doc: str | None = None
    created_by: str | None = None


class NoteUpdateRequest(BaseModel):
    content: str


class NoteResponse(BaseModel):
    id: str
    content: str
    entity_type: str
    entity_id: str
    provenance: str
    source_doc: str | None = None
    created_by: str | None = None
    created_at: str
    updated_at: str


class NoteListResponse(BaseModel):
    notes: list[NoteResponse]
    total: int


class BatchNoteRequest(BaseModel):
    entity_type: str
    entity_ids: list[str]


class BatchNoteResponse(BaseModel):
    notes_by_entity: dict[str, list[NoteResponse]]


def _note_resp(note: Note) -> NoteResponse:
    return NoteResponse(id=note.id, content=note.content, entity_type=note.entity_type, entity_id=note.entity_id, provenance=note.provenance.value, source_doc=note.source_doc, created_by=note.created_by, created_at=note.created_at.isoformat(), updated_at=note.updated_at.isoformat())


notes_router = APIRouter(prefix="/notes", tags=["notes"])


@notes_router.get("", response_model=NoteListResponse)
async def list_notes(entity_type: str, entity_id: str, c: Ctr) -> NoteListResponse:
    notes = await c.property_store.list_notes(entity_type=entity_type, entity_id=entity_id)
    notes.sort(key=lambda n: n.created_at, reverse=True)
    return NoteListResponse(notes=[_note_resp(n) for n in notes], total=len(notes))


@notes_router.post("/batch", response_model=BatchNoteResponse)
async def batch_notes(body: BatchNoteRequest, c: Ctr) -> BatchNoteResponse:
    by_entity: dict[str, list[NoteResponse]] = {eid: [] for eid in body.entity_ids}
    for entity_id in body.entity_ids:
        notes = await c.property_store.list_notes(entity_type=body.entity_type, entity_id=entity_id)
        notes.sort(key=lambda n: n.created_at, reverse=True)
        by_entity[entity_id] = [_note_resp(n) for n in notes]
    return BatchNoteResponse(notes_by_entity=by_entity)


@notes_router.post("", response_model=NoteResponse, status_code=201)
async def create_note(body: NoteCreateRequest, c: Ctr) -> NoteResponse:
    now = datetime.now(UTC)
    note = Note(id=f"note:{uuid.uuid4().hex[:12]}", content=body.content, entity_type=body.entity_type, entity_id=body.entity_id, provenance=body.provenance, source_doc=body.source_doc, created_by=body.created_by, created_at=now, updated_at=now)
    result = await c.property_store.upsert_note(note)
    return _note_resp(result.entity)


@notes_router.patch("/{note_id}", response_model=NoteResponse)
async def update_note(note_id: str, body: NoteUpdateRequest, c: Ctr) -> NoteResponse:
    existing = await c.property_store.get_note(note_id)
    if not existing:
        raise NotFoundError("Note", note_id)
    updated = existing.model_copy(update={"content": body.content, "updated_at": datetime.now(UTC)})
    result = await c.property_store.upsert_note(updated)
    return _note_resp(result.entity)


@notes_router.delete("/{note_id}", status_code=200)
async def delete_note(note_id: str, c: Ctr) -> DeletedResponse:
    existing = await c.property_store.get_note(note_id)
    if not existing:
        raise NotFoundError("Note", note_id)
    await c.property_store.delete_note(note_id)
    return DeletedResponse()
