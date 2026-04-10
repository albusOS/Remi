"""Operations — delinquency board from balance observations."""

from __future__ import annotations

import asyncio

from remi.application.core.models import BalanceObservation
from remi.application.core.protocols import PropertyStore
from remi.application.portfolio.properties import property_ids_for_manager

from .views import DelinquencyBoard, DelinquentTenant


def _latest_obs_by_tenant(
    obs_list: list[BalanceObservation],
) -> dict[str, BalanceObservation]:
    latest: dict[str, BalanceObservation] = {}
    for obs in obs_list:
        existing = latest.get(obs.tenant_id)
        if existing is None or obs.observed_at > existing.observed_at:
            latest[obs.tenant_id] = obs
    return latest


class DelinquencyResolver:
    """Delinquency board — tenants with outstanding balances."""

    def __init__(self, property_store: PropertyStore) -> None:
        self._ps = property_store

    async def delinquency_board(
        self,
        manager_id: str | None = None,
        property_ids: set[str] | None = None,
    ) -> DelinquencyBoard:
        allowed: set[str] | None = property_ids
        if allowed is None and manager_id:
            allowed = await property_ids_for_manager(self._ps, manager_id)

        all_obs = await self._ps.list_balance_observations()
        if allowed is not None:
            all_obs = [o for o in all_obs if o.property_id in allowed]

        latest_obs = _latest_obs_by_tenant(all_obs)
        delinquent = [obs for obs in latest_obs.values() if obs.balance_total > 0]
        delinquent.sort(key=lambda o: o.balance_total, reverse=True)

        tenant_ids = list({obs.tenant_id for obs in delinquent})
        prop_ids = list({obs.property_id for obs in delinquent})

        tenants_list, props_list = await asyncio.gather(
            asyncio.gather(*[self._ps.get_tenant(tid) for tid in tenant_ids]),
            asyncio.gather(*[self._ps.get_property(pid) for pid in prop_ids]),
        )
        tenant_map = {tid: t for tid, t in zip(tenant_ids, tenants_list, strict=True) if t}
        prop_map = {pid: p for pid, p in zip(prop_ids, props_list, strict=True) if p}

        mgr_ids = list({p.manager_id for p in prop_map.values() if p.manager_id})
        mgr_res = await asyncio.gather(*[self._ps.get_manager(mid) for mid in mgr_ids])
        mgr_map = {mid: m for mid, m in zip(mgr_ids, mgr_res, strict=True) if m}

        delinquency_notes = await self._load_delinquency_notes(
            [obs.tenant_id for obs in delinquent]
        )

        result_items: list[DelinquentTenant] = []
        for obs in delinquent:
            tenant = tenant_map.get(obs.tenant_id)
            prop = prop_map.get(obs.property_id)
            mgr_id = prop.manager_id if prop else None
            mgr = mgr_map.get(mgr_id) if mgr_id else None
            result_items.append(
                DelinquentTenant(
                    tenant_id=obs.tenant_id,
                    tenant_name=tenant.name if tenant else obs.tenant_id,
                    status=tenant.status.value if tenant else "unknown",
                    property_id=obs.property_id,
                    property_name=prop.name if prop else obs.property_id,
                    manager_id=mgr_id,
                    manager_name=mgr.name if mgr else None,
                    balance_owed=float(obs.balance_total),
                    balance_0_30=float(obs.balance_0_30),
                    balance_30_plus=float(obs.balance_30_plus),
                    last_payment_date=obs.last_payment_date.isoformat()
                    if obs.last_payment_date
                    else None,
                    delinquency_notes=delinquency_notes.get(obs.tenant_id),
                )
            )

        return DelinquencyBoard(
            total_delinquent=len(result_items),
            total_balance=float(sum(obs.balance_total for obs in delinquent)),
            tenants=result_items,
        )

    async def _load_delinquency_notes(self, tenant_ids: list[str]) -> dict[str, str]:
        result: dict[str, str] = {}
        for tid in tenant_ids:
            notes = await self._ps.list_notes(entity_type="Tenant", entity_id=tid)
            for note in notes:
                if "delinquency" in (note.content or "").lower():
                    result[tid] = note.content
                    break
        return result
