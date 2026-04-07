"""REST endpoints for leases."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter

from remi.application.api.schemas import (
    CreateLeaseRequest,
    CreateLeaseResponse,
    UpdateLeaseRequest,
)
from remi.application.api.shared_schemas import DeletedResponse, UpdatedResponse
from remi.application.core.models import Lease, LeaseStatus, RenewalStatus
from remi.application.views import (
    LeaseCalendar,
    LeaseListResult,
)
from remi.shell.api.dependencies import Ctr
from remi.types.errors import NotFoundError
from remi.types.identity import lease_id as _lease_id

router = APIRouter(prefix="/leases", tags=["leases"])


@router.get("", response_model=LeaseListResult)
async def list_leases(
    c: Ctr,
    property_id: str | None = None,
    status: str | None = None,
) -> LeaseListResult:
    return await c.lease_resolver.list_leases(property_id=property_id, status=status)


@router.get("/expiring", response_model=LeaseCalendar)
async def expiring_leases(
    c: Ctr,
    days: int = 60,
) -> LeaseCalendar:
    return await c.lease_resolver.expiring_leases(days=days)


@router.post("", response_model=CreateLeaseResponse, status_code=201)
async def create_lease(
    body: CreateLeaseRequest,
    c: Ctr,
) -> CreateLeaseResponse:
    unit = await c.property_store.get_unit(body.unit_id)
    if not unit:
        raise NotFoundError("Unit", body.unit_id)
    tenant = await c.property_store.get_tenant(body.tenant_id)
    if not tenant:
        raise NotFoundError("Tenant", body.tenant_id)

    lid = _lease_id(tenant.name, body.property_id, unit.unit_number)
    lease = Lease(
        id=lid,
        unit_id=body.unit_id,
        tenant_id=body.tenant_id,
        property_id=body.property_id,
        start_date=date.fromisoformat(body.start_date),
        end_date=date.fromisoformat(body.end_date),
        monthly_rent=Decimal(str(body.monthly_rent)),
        deposit=Decimal(str(body.deposit)),
        status=LeaseStatus(body.status),
    )
    await c.property_store.upsert_lease(lease)
    return CreateLeaseResponse(
        lease_id=lid,
        unit_id=body.unit_id,
        tenant_id=body.tenant_id,
        property_id=body.property_id,
    )


@router.patch("/{lease_id}")
async def update_lease(
    lease_id: str,
    body: UpdateLeaseRequest,
    c: Ctr,
) -> UpdatedResponse:
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


@router.delete("/{lease_id}", status_code=200)
async def delete_lease(
    lease_id: str,
    c: Ctr,
) -> DeletedResponse:
    deleted = await c.property_store.delete_lease(lease_id)
    if not deleted:
        raise NotFoundError("Lease", lease_id)
    return DeletedResponse()
