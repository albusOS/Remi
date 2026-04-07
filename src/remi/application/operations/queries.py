"""Operations queries — LeaseResolver, MaintenanceResolver."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from decimal import Decimal

from remi.application.core.models import LeaseStatus, MaintenanceStatus
from remi.application.core.protocols import PropertyStore
from remi.application.portfolio.models import ExpiringLease, LeaseCalendar

from .models import (
    LeaseInfo,
    LeaseListItem,
    LeaseListResult,
    MaintenanceItem,
    MaintenanceListResult,
    MaintenanceSummaryResult,
    TenantDetail,
)


class LeaseResolver:
    """Entity resolver for leases."""

    def __init__(self, property_store: PropertyStore) -> None:
        self._ps = property_store

    async def list_leases(
        self,
        property_id: str | None = None,
        status: str | None = None,
    ) -> LeaseListResult:
        lease_status = LeaseStatus(status) if status else None
        leases = await self._ps.list_leases(property_id=property_id, status=lease_status)
        items: list[LeaseListItem] = []
        for le in leases:
            tenant = await self._ps.get_tenant(le.tenant_id)
            items.append(
                LeaseListItem(
                    id=le.id,
                    tenant=tenant.name if tenant else le.tenant_id,
                    unit_id=le.unit_id,
                    property_id=le.property_id,
                    start=le.start_date.isoformat(),
                    end=le.end_date.isoformat(),
                    rent=float(le.monthly_rent),
                    status=le.status.value,
                )
            )
        return LeaseListResult(count=len(items), leases=items)

    async def expiring_leases(self, days: int = 60) -> LeaseCalendar:
        today = date.today()
        deadline = today + timedelta(days=days)
        leases = await self._ps.list_leases(status=LeaseStatus.ACTIVE)
        expiring = [le for le in leases if le.end_date <= deadline or le.is_month_to_month]
        expiring.sort(key=lambda le: le.end_date)

        tenant_ids = list({le.tenant_id for le in expiring})
        prop_ids = list({le.property_id for le in expiring})
        unit_ids = list({le.unit_id for le in expiring})

        tenants_res, props_res, units_res = await asyncio.gather(
            asyncio.gather(*[self._ps.get_tenant(tid) for tid in tenant_ids]),
            asyncio.gather(*[self._ps.get_property(pid) for pid in prop_ids]),
            asyncio.gather(*[self._ps.get_unit(uid) for uid in unit_ids]),
        )
        tenant_map = {tid: t for tid, t in zip(tenant_ids, tenants_res, strict=True) if t}
        prop_map = {pid: p for pid, p in zip(prop_ids, props_res, strict=True) if p}
        unit_map = {uid: u for uid, u in zip(unit_ids, units_res, strict=True) if u}

        items: list[ExpiringLease] = []
        mtm_count = 0
        for le in expiring:
            tenant = tenant_map.get(le.tenant_id)
            prop = prop_map.get(le.property_id)
            unit = unit_map.get(le.unit_id)
            if le.is_month_to_month:
                mtm_count += 1
            items.append(
                ExpiringLease(
                    lease_id=le.id,
                    tenant_name=tenant.name if tenant else le.tenant_id,
                    property_id=le.property_id,
                    property_name=prop.name if prop else le.property_id,
                    unit_id=le.unit_id,
                    unit_number=unit.unit_number if unit else le.unit_id,
                    monthly_rent=float(le.monthly_rent),
                    market_rent=float(le.market_rent),
                    end_date=le.end_date.isoformat(),
                    days_left=(le.end_date - today).days,
                    is_month_to_month=le.is_month_to_month,
                )
            )

        return LeaseCalendar(
            days_window=days,
            total_expiring=len(items),
            month_to_month_count=mtm_count,
            leases=items,
        )

    async def tenant_detail(self, tenant_id: str) -> TenantDetail | None:
        tenant = await self._ps.get_tenant(tenant_id)
        if not tenant:
            return None
        leases = await self._ps.list_leases(tenant_id=tenant_id)
        lease_info: list[LeaseInfo] = []
        for le in leases:
            unit = await self._ps.get_unit(le.unit_id)
            lease_info.append(
                LeaseInfo(
                    lease_id=le.id,
                    unit=unit.unit_number if unit else le.unit_id,
                    property_id=le.property_id,
                    start=le.start_date.isoformat(),
                    end=le.end_date.isoformat(),
                    monthly_rent=float(le.monthly_rent),
                    status=le.status.value,
                )
            )
        return TenantDetail(
            tenant_id=tenant_id,
            name=tenant.name,
            email=tenant.email,
            phone=tenant.phone,
            leases=lease_info,
        )


class MaintenanceResolver:
    """Entity resolver for maintenance requests."""

    def __init__(self, property_store: PropertyStore) -> None:
        self._ps = property_store

    async def list_maintenance(
        self,
        property_id: str | None = None,
        unit_id: str | None = None,
        manager_id: str | None = None,
        status: str | None = None,
    ) -> MaintenanceListResult:
        maint_status = MaintenanceStatus(status) if status else None
        requests = await self._ps.list_maintenance_requests(
            property_id=property_id, unit_id=unit_id, manager_id=manager_id, status=maint_status,
        )
        requests.sort(key=lambda r: r.created_at, reverse=True)
        return MaintenanceListResult(
            count=len(requests),
            requests=[
                MaintenanceItem(
                    id=r.id, property_id=r.property_id, unit_id=r.unit_id,
                    title=r.title, description=r.description,
                    category=r.category.value, priority=r.priority.value,
                    status=r.status.value,
                    source=r.source.value if r.source else None,
                    vendor=r.vendor,
                    cost=float(r.cost) if r.cost else None,
                    scheduled_date=r.scheduled_date.isoformat() if r.scheduled_date else None,
                    completed_date=r.completed_date.isoformat() if r.completed_date else None,
                    created=r.created_at.isoformat(),
                    resolved=r.resolved_at.isoformat() if r.resolved_at else None,
                )
                for r in requests
            ],
        )

    async def maintenance_summary(
        self,
        property_id: str | None = None,
        unit_id: str | None = None,
        manager_id: str | None = None,
    ) -> MaintenanceSummaryResult:
        requests = await self._ps.list_maintenance_requests(
            property_id=property_id, unit_id=unit_id, manager_id=manager_id,
        )
        by_status: dict[str, int] = {}
        by_category: dict[str, int] = {}
        total_cost = Decimal("0")
        for r in requests:
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1
            by_category[r.category.value] = by_category.get(r.category.value, 0) + 1
            if r.cost:
                total_cost += r.cost
        return MaintenanceSummaryResult(total=len(requests), by_status=by_status, by_category=by_category, total_cost=float(total_cost))
