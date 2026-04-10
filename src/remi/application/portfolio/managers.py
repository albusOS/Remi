"""Portfolio — manager aggregation, summaries, and rankings."""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal

from remi.application.core.models import Lease, LeaseStatus, MaintenanceRequest, Unit
from remi.application.core.protocols import PropertyStore
from remi.application.core.rules import (
    active_lease,
    is_below_market,
    is_maintenance_open,
    is_occupied,
    is_vacant,
    loss_to_lease,
)

from .views import (
    ManagerMetrics,
    ManagerRanking,
    ManagerSummary,
    PropertySummary,
    UnitIssue,
)


def _group_by_unit(leases: list[Lease]) -> dict[str, list[Lease]]:
    result: dict[str, list[Lease]] = {}
    for le in leases:
        result.setdefault(le.unit_id, []).append(le)
    return result


def _latest_obs_by_tenant(obs_list: list) -> dict[str, object]:
    latest: dict[str, object] = {}
    for obs in obs_list:
        existing = latest.get(obs.tenant_id)
        if existing is None or obs.observed_at > existing.observed_at:  # type: ignore[union-attr]
            latest[obs.tenant_id] = obs
    return latest


class ManagerResolver:
    """Director-level portfolio roll-up over PropertyStore."""

    def __init__(self, property_store: PropertyStore) -> None:
        self._ps = property_store

    async def aggregate_manager(self, manager_id: str) -> ManagerSummary | None:
        manager = await self._ps.get_manager(manager_id)
        if not manager:
            return None

        all_properties = await self._ps.list_properties(manager_id=manager_id)
        today = date.today()

        total_units = 0
        occupied = 0
        vacant = 0
        total_market = Decimal("0")
        total_actual = Decimal("0")
        total_loss_to_lease_val = Decimal("0")
        total_vacancy_loss = Decimal("0")
        open_maintenance = 0
        emergency_maintenance = 0
        expiring_leases_90d = 0
        expired_leases = 0
        below_market_units = 0
        property_count = 0

        property_summaries: list[PropertySummary] = []
        top_issues: list[UnitIssue] = []

        async def _load_prop(
            prop_id: str,
        ) -> tuple[list[Unit], list[Lease], list[MaintenanceRequest]]:
            u, le, m = await asyncio.gather(
                self._ps.list_units(property_id=prop_id),
                self._ps.list_leases(property_id=prop_id),
                self._ps.list_maintenance_requests(property_id=prop_id),
            )
            return u, le, m

        prop_data = await asyncio.gather(*[_load_prop(prop.id) for prop in all_properties])

        for prop, (units, leases, maint) in zip(all_properties, prop_data, strict=True):
            property_count += 1
            leases_by_unit = _group_by_unit(leases)

            p_units = len(units)
            p_occ = sum(1 for u in units if is_occupied(leases_by_unit.get(u.id, [])))
            p_vac = sum(1 for u in units if is_vacant(leases_by_unit.get(u.id, [])))
            p_market = sum((u.market_rent for u in units), Decimal("0"))
            p_actual = sum(
                (
                    act.monthly_rent
                    for u in units
                    if (act := active_lease(leases_by_unit.get(u.id, []))) is not None
                ),
                Decimal("0"),
            )
            p_ltl = sum(
                (
                    loss_to_lease(
                        u.market_rent,
                        active_lease(leases_by_unit.get(u.id, [])).monthly_rent
                        if active_lease(leases_by_unit.get(u.id, []))
                        else Decimal("0"),
                    )
                    for u in units
                ),
                Decimal("0"),
            )
            p_vloss = sum(
                (u.market_rent for u in units if is_vacant(leases_by_unit.get(u.id, []))),
                Decimal("0"),
            )
            p_open_maint = sum(1 for m in maint if is_maintenance_open(m))
            p_emergency = sum(
                1 for m in maint if is_maintenance_open(m) and m.priority.value == "emergency"
            )

            p_expiring = 0
            p_expired = 0
            for le in leases:
                if le.status == LeaseStatus.ACTIVE:
                    days_left = (le.end_date - today).days
                    if 0 < days_left <= 90:
                        p_expiring += 1
                elif le.status == LeaseStatus.EXPIRED:
                    p_expired += 1

            p_below = sum(
                1
                for u in units
                if is_below_market(
                    u.market_rent,
                    active_lease(leases_by_unit.get(u.id, [])).monthly_rent
                    if active_lease(leases_by_unit.get(u.id, []))
                    else Decimal("0"),
                )
            )

            total_units += p_units
            occupied += p_occ
            vacant += p_vac
            total_market += p_market
            total_actual += p_actual
            total_loss_to_lease_val += p_ltl
            total_vacancy_loss += p_vloss
            open_maintenance += p_open_maint
            emergency_maintenance += p_emergency
            expiring_leases_90d += p_expiring
            expired_leases += p_expired
            below_market_units += p_below

            issue_count = p_vac + p_open_maint + p_expiring + p_expired + p_below
            property_summaries.append(
                PropertySummary(
                    property_id=prop.id,
                    property_name=prop.name,
                    total_units=p_units,
                    occupied=p_occ,
                    vacant=p_vac,
                    occupancy_rate=round(p_occ / p_units, 3) if p_units else 0,
                    monthly_actual=float(p_actual),
                    monthly_market=float(p_market),
                    loss_to_lease=float(p_ltl),
                    vacancy_loss=float(p_vloss),
                    open_maintenance=p_open_maint,
                    emergency_maintenance=p_emergency,
                    expiring_leases=p_expiring,
                    expired_leases=p_expired,
                    below_market_units=p_below,
                    issue_count=issue_count,
                )
            )

            for u in units:
                unit_leases = leases_by_unit.get(u.id, [])
                act = active_lease(unit_leases)
                lease_rent = act.monthly_rent if act else Decimal("0")
                unit_issues: list[str] = []
                if is_vacant(unit_leases):
                    unit_issues.append("vacant")
                if is_below_market(u.market_rent, lease_rent):
                    unit_issues.append("below_market")
                unit_active = next(
                    (le for le in unit_leases if le.status == LeaseStatus.ACTIVE), None
                )
                if unit_active and 0 < (unit_active.end_date - today).days <= 90:
                    unit_issues.append("expiring_soon")
                if any(le.status == LeaseStatus.EXPIRED for le in unit_leases):
                    unit_issues.append("expired_lease")
                unit_maint = [m for m in maint if m.unit_id == u.id and is_maintenance_open(m)]
                if unit_maint:
                    unit_issues.append("open_maintenance")
                if unit_issues:
                    top_issues.append(
                        UnitIssue(
                            property_id=prop.id,
                            property_name=prop.name,
                            unit_id=u.id,
                            unit_number=u.unit_number,
                            issues=unit_issues,
                            monthly_impact=float(u.market_rent - lease_rent)
                            if lease_rent < u.market_rent
                            else 0,
                        )
                    )

        property_summaries.sort(key=lambda p: p.issue_count, reverse=True)
        top_issues.sort(key=lambda i: len(i.issues), reverse=True)

        all_property_ids = {p.property_id for p in property_summaries}

        all_obs = await self._ps.list_balance_observations()
        latest_obs = _latest_obs_by_tenant(all_obs)
        delinquent_count = 0
        delinquent_balance = Decimal("0")
        for obs in latest_obs.values():
            if obs.property_id in all_property_ids and obs.balance_total > 0:  # type: ignore[union-attr]
                delinquent_count += 1
                delinquent_balance += obs.balance_total  # type: ignore[union-attr]

        metrics = ManagerMetrics(
            total_units=total_units,
            occupied=occupied,
            vacant=vacant,
            occupancy_rate=round(occupied / total_units, 3) if total_units else 0,
            total_actual_rent=float(total_actual),
            total_market_rent=float(total_market),
            loss_to_lease=float(total_loss_to_lease_val),
            vacancy_loss=float(total_vacancy_loss),
            open_maintenance=open_maintenance,
            expiring_leases_90d=expiring_leases_90d,
        )

        return ManagerSummary(
            manager_id=manager.id,
            name=manager.name,
            email=manager.email,
            company=manager.company,
            property_count=property_count,
            metrics=metrics,
            delinquent_count=delinquent_count,
            total_delinquent_balance=float(delinquent_balance),
            expired_leases=expired_leases,
            below_market_units=below_market_units,
            emergency_maintenance=emergency_maintenance,
            properties=property_summaries,
            top_issues=top_issues[:20],
        )

    async def list_manager_summaries(self) -> list[ManagerSummary]:
        managers = await self._ps.list_managers()
        summaries = await asyncio.gather(*[self.aggregate_manager(m.id) for m in managers])
        return [s for s in summaries if s is not None]

    async def rank_managers(
        self,
        sort_by: str = "delinquency_rate",
        ascending: bool = False,
        limit: int | None = None,
    ) -> list[ManagerRanking]:
        summaries = await self.list_manager_summaries()
        rows: list[ManagerRanking] = []
        for s in summaries:
            delinquency_rate = (
                round(s.delinquent_count / s.metrics.total_units, 4)
                if s.metrics.total_units
                else 0.0
            )
            rows.append(
                ManagerRanking(
                    manager_id=s.manager_id,
                    name=s.name,
                    property_count=s.property_count,
                    metrics=s.metrics,
                    delinquent_count=s.delinquent_count,
                    total_delinquent_balance=s.total_delinquent_balance,
                    delinquency_rate=delinquency_rate,
                )
            )

        ranking_keys = set(ManagerRanking.model_fields.keys())
        metrics_keys = set(ManagerMetrics.model_fields.keys())
        if sort_by in ranking_keys:
            rows.sort(key=lambda r: getattr(r, sort_by, 0), reverse=not ascending)
        elif sort_by in metrics_keys:
            rows.sort(key=lambda r: getattr(r.metrics, sort_by, 0), reverse=not ascending)
        else:
            rows.sort(key=lambda r: r.delinquency_rate, reverse=not ascending)

        if limit and limit > 0:
            rows = rows[:limit]
        return rows
