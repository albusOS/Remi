"""Portfolio queries — ManagerResolver, PropertyResolver, RentRollResolver, scope helpers."""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from typing import Any

from remi.application.core.models import Lease, LeaseStatus, MaintenanceRequest, Unit
from remi.application.core.protocols import PropertyStore
from remi.application.core.rules import (
    active_lease,
    derive_occupancy_status,
    is_below_market,
    is_maintenance_open,
    is_occupied,
    is_vacant,
    loss_to_lease,
    pct_below_market,
)

from .models import (
    LeaseInRentRoll,
    MaintenanceInRentRoll,
    ManagerMetrics,
    ManagerRanking,
    ManagerSummary,
    PropertyDetail,
    PropertyDetailUnit,
    PropertyListItem,
    PropertySummary,
    RentRollResult,
    RentRollRow,
    TenantInRentRoll,
    UnitIssue,
    UnitListItem,
    UnitListResult,
)


# ---------------------------------------------------------------------------
# Scope helpers
# ---------------------------------------------------------------------------


async def property_ids_for_manager(store: PropertyStore, manager_id: str) -> set[str]:
    props = await store.list_properties(manager_id=manager_id)
    return {p.id for p in props}


async def property_ids_for_owner(store: PropertyStore, owner_id: str) -> set[str]:
    props = await store.list_properties(owner_id=owner_id)
    return {p.id for p in props}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# ManagerResolver
# ---------------------------------------------------------------------------


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

        for prop, (units, leases, maint) in zip(
            all_properties,
            prop_data,
            strict=True,
        ):
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
            if obs.property_id in all_property_ids and obs.balance_total > 0:
                delinquent_count += 1
                delinquent_balance += obs.balance_total

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


# ---------------------------------------------------------------------------
# PropertyResolver
# ---------------------------------------------------------------------------


class PropertyResolver:
    """Entity resolver for properties."""

    def __init__(self, property_store: PropertyStore) -> None:
        self._ps = property_store

    async def list_properties(
        self,
        *,
        manager_id: str | None = None,
        owner_id: str | None = None,
    ) -> list[PropertyListItem]:
        properties = await self._ps.list_properties(
            manager_id=manager_id,
            owner_id=owner_id,
        )
        items: list[PropertyListItem] = []
        for p in properties:
            units = await self._ps.list_units(property_id=p.id)
            all_leases = await self._ps.list_leases(property_id=p.id)
            leases_by_unit = _group_by_unit(all_leases)
            occ = sum(1 for u in units if is_occupied(leases_by_unit.get(u.id, [])))

            o_name: str | None = None
            if p.owner_id:
                owner = await self._ps.get_owner(p.owner_id)
                if owner:
                    o_name = owner.name

            items.append(
                PropertyListItem(
                    id=p.id,
                    name=p.name,
                    address=p.address.one_line(),
                    type=p.property_type.value,
                    year_built=p.year_built,
                    total_units=len(units),
                    occupied=occ,
                    manager_id=p.manager_id,
                    owner_id=p.owner_id,
                    owner_name=o_name,
                )
            )
        return items

    async def get_property_detail(self, property_id: str) -> PropertyDetail | None:
        prop = await self._ps.get_property(property_id)
        if not prop:
            return None

        units = await self._ps.list_units(property_id=property_id)
        all_leases = await self._ps.list_leases(property_id=property_id)
        active_leases = [le for le in all_leases if le.status == LeaseStatus.ACTIVE]
        leases_by_unit = _group_by_unit(all_leases)

        occupied_count = sum(1 for u in units if is_occupied(leases_by_unit.get(u.id, [])))
        vacant_count = len(units) - occupied_count
        revenue = sum(
            (le.monthly_rent for le in active_leases),
            Decimal("0"),
        )

        manager_id: str | None = None
        manager_name: str | None = None
        if prop.manager_id:
            mgr = await self._ps.get_manager(prop.manager_id)
            if mgr:
                manager_id = mgr.id
                manager_name = mgr.name

        o_id: str | None = None
        o_name: str | None = None
        if prop.owner_id:
            owner = await self._ps.get_owner(prop.owner_id)
            if owner:
                o_id = owner.id
                o_name = owner.name

        unit_rows: list[PropertyDetailUnit] = []
        for u in units:
            unit_leases = leases_by_unit.get(u.id, [])
            act = active_lease(unit_leases)
            occ_status = derive_occupancy_status(unit_leases)
            unit_rows.append(
                PropertyDetailUnit(
                    id=u.id,
                    property_id=property_id,
                    unit_number=u.unit_number,
                    status="occupied" if act else "vacant",
                    occupancy_status=occ_status.value,
                    bedrooms=u.bedrooms,
                    bathrooms=u.bathrooms,
                    sqft=u.sqft,
                    floor=u.floor,
                    market_rent=float(u.market_rent),
                    current_rent=float(act.monthly_rent) if act else 0.0,
                )
            )

        return PropertyDetail(
            id=property_id,
            name=prop.name,
            address=prop.address,
            property_type=prop.property_type.value,
            year_built=prop.year_built,
            manager_id=manager_id,
            manager_name=manager_name,
            owner_id=o_id,
            owner_name=o_name,
            total_units=len(units),
            occupied=occupied_count,
            vacant=vacant_count,
            occupancy_rate=round(occupied_count / len(units), 3) if units else 0,
            monthly_revenue=float(revenue),
            active_leases=len(active_leases),
            units=unit_rows,
        )

    async def list_all_units(
        self,
        property_id: str | None = None,
    ) -> UnitListResult:
        units = await self._ps.list_units(property_id=property_id)
        if not units:
            return UnitListResult(count=0, units=[])

        all_leases = await self._ps.list_leases(property_id=property_id)
        leases_by_unit = _group_by_unit(all_leases)

        items: list[UnitListItem] = []
        for u in units:
            prop = await self._ps.get_property(u.property_id)
            unit_leases = leases_by_unit.get(u.id, [])
            act = active_lease(unit_leases)
            items.append(
                UnitListItem(
                    id=u.id,
                    unit_number=u.unit_number,
                    property_name=prop.name if prop else u.property_id,
                    property_id=u.property_id,
                    status="occupied" if is_occupied(unit_leases) else "vacant",
                    bedrooms=u.bedrooms,
                    sqft=u.sqft,
                    market_rent=float(u.market_rent),
                    current_rent=float(act.monthly_rent) if act else 0.0,
                )
            )
        return UnitListResult(count=len(items), units=items)


# ---------------------------------------------------------------------------
# RentRollResolver
# ---------------------------------------------------------------------------


class RentRollResolver:
    """Builds a detailed rent-roll view for a property."""

    def __init__(self, property_store: PropertyStore) -> None:
        self._ps = property_store

    async def build_rent_roll(self, property_id: str) -> RentRollResult | None:
        prop = await self._ps.get_property(property_id)
        if not prop:
            return None

        units = await self._ps.list_units(property_id=property_id)
        all_leases = await self._ps.list_leases(property_id=property_id)
        all_maintenance = await self._ps.list_maintenance_requests(property_id=property_id)

        leases_by_unit: dict[str, list] = {}
        for le in all_leases:
            leases_by_unit.setdefault(le.unit_id, []).append(le)

        tenant_cache: dict[str, Any] = {}
        today = date.today()
        rows: list[RentRollRow] = []
        total_market = Decimal("0")
        total_actual = Decimal("0")
        total_ltl = Decimal("0")
        total_vacancy_loss = Decimal("0")

        for unit in units:
            unit_leases = leases_by_unit.get(unit.id, [])
            act = active_lease(unit_leases)
            current_lease = act or next(
                (le for le in unit_leases if le.status == LeaseStatus.EXPIRED), None
            )
            lease_rent = act.monthly_rent if act else Decimal("0")

            tenant = None
            if current_lease:
                tid = current_lease.tenant_id
                if tid not in tenant_cache:
                    tenant_cache[tid] = await self._ps.get_tenant(tid)
                tenant = tenant_cache[tid]

            open_maint = [
                mr for mr in all_maintenance if mr.unit_id == unit.id and is_maintenance_open(mr)
            ]

            rent_gap = float(lease_rent - unit.market_rent)
            pct_below = pct_below_market(unit.market_rent, lease_rent)

            days_to_expiry: int | None = None
            if current_lease:
                days_to_expiry = (current_lease.end_date - today).days

            issues: list[str] = []
            if is_vacant(unit_leases):
                issues.append("vacant")
            if is_below_market(unit.market_rent, lease_rent):
                issues.append("below_market")
            if current_lease and current_lease.status == LeaseStatus.EXPIRED:
                issues.append("expired_lease")
            if days_to_expiry is not None and 0 < days_to_expiry <= 90:
                issues.append("expiring_soon")
            if open_maint:
                issues.append("open_maintenance")

            total_market += unit.market_rent
            total_actual += lease_rent
            total_ltl += loss_to_lease(unit.market_rent, lease_rent)
            if is_vacant(unit_leases):
                total_vacancy_loss += unit.market_rent

            rows.append(
                RentRollRow(
                    unit_id=unit.id,
                    unit_number=unit.unit_number,
                    floor=unit.floor,
                    bedrooms=unit.bedrooms,
                    bathrooms=unit.bathrooms,
                    sqft=unit.sqft,
                    status="occupied" if act else "vacant",
                    market_rent=float(unit.market_rent),
                    current_rent=float(lease_rent),
                    rent_gap=rent_gap,
                    pct_below_market=pct_below,
                    lease=LeaseInRentRoll(
                        id=current_lease.id,
                        status=current_lease.status.value,
                        start_date=current_lease.start_date.isoformat(),
                        end_date=current_lease.end_date.isoformat(),
                        monthly_rent=float(current_lease.monthly_rent),
                        deposit=float(current_lease.deposit),
                        days_to_expiry=days_to_expiry,
                    )
                    if current_lease
                    else None,
                    tenant=TenantInRentRoll(
                        id=tenant.id,
                        name=tenant.name,
                        email=tenant.email,
                        phone=tenant.phone,
                    )
                    if tenant
                    else None,
                    open_maintenance=len(open_maint),
                    maintenance_items=[
                        MaintenanceInRentRoll(
                            id=mr.id,
                            title=mr.title,
                            category=mr.category.value,
                            priority=mr.priority.value,
                            status=mr.status.value,
                            cost=float(mr.cost) if mr.cost else None,
                        )
                        for mr in open_maint
                    ],
                    issues=issues,
                )
            )

        rows.sort(key=lambda r: len(r.issues), reverse=True)

        return RentRollResult(
            property_id=property_id,
            property_name=prop.name,
            total_units=len(units),
            occupied=sum(1 for u in units if is_occupied(leases_by_unit.get(u.id, []))),
            vacant=sum(1 for u in units if is_vacant(leases_by_unit.get(u.id, []))),
            total_market_rent=float(total_market),
            total_actual_rent=float(total_actual),
            total_loss_to_lease=float(total_ltl),
            total_vacancy_loss=float(total_vacancy_loss),
            rows=rows,
        )
