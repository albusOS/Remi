"""REST endpoints for tenant queries."""

from __future__ import annotations

from fastapi import APIRouter

from remi.application.api.schemas import (
    CreateTenantRequest,
    CreateTenantResponse,
    UpdateTenantRequest,
)
from remi.application.api.shared_schemas import DeletedResponse, UpdatedResponse
from remi.application.core.models import Tenant, TenantStatus
from remi.application.views import TenantDetail
from remi.shell.api.dependencies import Ctr
from remi.types.errors import NotFoundError
from remi.types.identity import tenant_id as _tenant_id

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/{tenant_id}", response_model=TenantDetail)
async def get_tenant(
    tenant_id: str,
    c: Ctr,
) -> TenantDetail:
    detail = await c.lease_resolver.tenant_detail(tenant_id)
    if not detail:
        raise NotFoundError("Tenant", tenant_id)
    return detail


@router.post("", response_model=CreateTenantResponse, status_code=201)
async def create_tenant(
    body: CreateTenantRequest,
    c: Ctr,
) -> CreateTenantResponse:
    tid = _tenant_id(body.name, body.property_id)
    tenant = Tenant(
        id=tid,
        name=body.name,
        email=body.email,
        phone=body.phone,
    )
    await c.property_store.upsert_tenant(tenant)
    return CreateTenantResponse(tenant_id=tid, name=body.name)


@router.patch("/{tenant_id}")
async def update_tenant(
    tenant_id: str,
    body: UpdateTenantRequest,
    c: Ctr,
) -> UpdatedResponse:
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


@router.delete("/{tenant_id}", status_code=200)
async def delete_tenant(
    tenant_id: str,
    c: Ctr,
) -> DeletedResponse:
    deleted = await c.property_store.delete_tenant(tenant_id)
    if not deleted:
        raise NotFoundError("Tenant", tenant_id)
    return DeletedResponse()
