"""Operations — lease list, expiring leases, and tenant detail."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta

from remi.application.core.models import LeaseStatus
from remi.application.core.protocols import PropertyStore

from .views import (
    ExpiringLease,
    LeaseCalendar,
    LeaseInfo,
    LeaseListItem,
    LeaseListResult,
    TenantDetail,
)


async def _property_ids_for_manager(ps: PropertyStore, manager_id: str) -> set[str]:
    props = await ps.list_properties(manager_id=manager_id)
    return {p.id for p in props}


class LeaseResolver:
    """Lease list, expiring calendar, and tenant detail."""

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

    async def expiring_leases(
        self,
        days: int = 90,
        manager_id: str | None = None,
        property_ids: set[str] | None = None,
    ) -> LeaseCalendar:
        """Leases expiring within *days* or on month-to-month terms."""
        today = date.today()
        deadline = today + timedelta(days=days)
        leases = await self._ps.list_leases(status=LeaseStatus.ACTIVE)

        allowed: set[str] | None = property_ids
        if allowed is None and manager_id:
            allowed = await _property_ids_for_manager(self._ps, manager_id)
        if allowed is not None:
            leases = [le for le in leases if le.property_id in allowed]

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

        mgr_ids = list({p.manager_id for p in prop_map.values() if p.manager_id})
        mgr_res = await asyncio.gather(*[self._ps.get_manager(mid) for mid in mgr_ids])
        mgr_map = {mid: m for mid, m in zip(mgr_ids, mgr_res, strict=True) if m}

        items: list[ExpiringLease] = []
        mtm_count = 0
        for le in expiring:
            tenant = tenant_map.get(le.tenant_id)
            prop = prop_map.get(le.property_id)
            unit = unit_map.get(le.unit_id)
            mgr_id = prop.manager_id if prop else None
            mgr = mgr_map.get(mgr_id) if mgr_id else None
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
                    manager_id=mgr_id,
                    manager_name=mgr.name if mgr else None,
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
