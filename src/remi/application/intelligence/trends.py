"""Intelligence — time-series trend analysis across delinquency, occupancy, rent, maintenance."""

from __future__ import annotations

import asyncio

from remi.application.core.models import BalanceObservation, LeaseStatus
from remi.application.core.protocols import PropertyStore
from remi.application.portfolio.properties import property_ids_for_manager

from .views import (
    DelinquencyTrend,
    MaintenanceTrend,
    MaintenanceTrendPeriod,
    OccupancyTrend,
    OccupancyTrendPeriod,
    RentTrend,
    RentTrendPeriod,
    TrendPeriod,
)


def _compute_direction(values: list[float]) -> str:
    if len(values) < 2:
        return "insufficient_data"
    first_half = values[: len(values) // 2]
    second_half = values[len(values) // 2 :]
    if not first_half or not second_half:
        return "insufficient_data"
    avg_first = sum(first_half) / len(first_half)
    avg_second = sum(second_half) / len(second_half)
    if avg_first == 0:
        return "stable" if avg_second == 0 else "worsening"
    pct_change = (avg_second - avg_first) / abs(avg_first)
    if pct_change > 0.05:
        return "worsening"
    if pct_change < -0.05:
        return "improving"
    return "stable"


def _compute_direction_inverse(values: list[float]) -> str:
    raw = _compute_direction(values)
    if raw == "worsening":
        return "improving"
    if raw == "improving":
        return "worsening"
    return raw


def _latest_obs_by_tenant(
    obs_list: list[BalanceObservation],
) -> dict[str, BalanceObservation]:
    latest: dict[str, BalanceObservation] = {}
    for obs in obs_list:
        existing = latest.get(obs.tenant_id)
        if existing is None or obs.observed_at > existing.observed_at:
            latest[obs.tenant_id] = obs
    return latest


class TrendResolver:
    """Cross-slice time-series analytics over delinquency, occupancy, rent, and maintenance."""

    def __init__(self, property_store: PropertyStore) -> None:
        self._ps = property_store

    async def delinquency_trend(
        self,
        manager_id: str | None = None,
        property_id: str | None = None,
        periods: int = 12,
    ) -> DelinquencyTrend:
        all_obs = await self._ps.list_balance_observations()

        if property_id:
            all_obs = [o for o in all_obs if o.property_id == property_id]
        elif manager_id:
            allowed = await property_ids_for_manager(self._ps, manager_id)
            if allowed:
                all_obs = [o for o in all_obs if o.property_id in allowed]

        by_month: dict[str, list[BalanceObservation]] = {}
        for obs in all_obs:
            key = obs.observed_at.strftime("%Y-%m")
            by_month.setdefault(key, []).append(obs)

        sorted_months = sorted(by_month.keys())[-periods:]
        trend_periods: list[TrendPeriod] = []
        for month in sorted_months:
            month_obs = by_month[month]
            latest_per_tenant = _latest_obs_by_tenant(month_obs)
            delinquent = [o for o in latest_per_tenant.values() if o.balance_total > 0]
            if not delinquent:
                trend_periods.append(
                    TrendPeriod(period=month, total_balance=0.0, tenant_count=0, avg_balance=0.0, max_balance=0.0)
                )
                continue
            total = sum(float(o.balance_total) for o in delinquent)
            trend_periods.append(
                TrendPeriod(
                    period=month,
                    total_balance=round(total, 2),
                    tenant_count=len(delinquent),
                    avg_balance=round(total / len(delinquent), 2),
                    max_balance=round(max(float(o.balance_total) for o in delinquent), 2),
                )
            )

        return DelinquencyTrend(
            manager_id=manager_id,
            periods=trend_periods,
            period_count=len(trend_periods),
            direction=_compute_direction([p.total_balance for p in trend_periods]),
        )

    async def occupancy_trend(
        self,
        manager_id: str | None = None,
        property_id: str | None = None,
        periods: int = 12,
    ) -> OccupancyTrend:
        if property_id:
            properties = [await self._ps.get_property(property_id)]
            properties = [p for p in properties if p is not None]
        elif manager_id:
            properties = await self._ps.list_properties(manager_id=manager_id)
        else:
            properties = await self._ps.list_properties()

        all_units = await asyncio.gather(
            *[self._ps.list_units(property_id=p.id) for p in properties]
        )
        all_leases = await asyncio.gather(
            *[self._ps.list_leases(property_id=p.id) for p in properties]
        )

        total_unit_count = sum(len(ul) for ul in all_units)
        flat_leases = [le for lease_list in all_leases for le in lease_list]

        by_month: dict[str, set[str]] = {}
        for le in flat_leases:
            ts = le.last_confirmed_at or le.first_seen_at
            if ts is None:
                continue
            if le.status.value not in ("active", "expired", "terminated"):
                continue
            key = ts.strftime("%Y-%m")
            by_month.setdefault(key, set()).add(le.unit_id)

        sorted_months = sorted(by_month.keys())[-periods:]
        trend_periods: list[OccupancyTrendPeriod] = []
        for month in sorted_months:
            occupied = len(by_month[month])
            capped = min(occupied, total_unit_count)
            vacant = total_unit_count - capped
            trend_periods.append(
                OccupancyTrendPeriod(
                    period=month,
                    total_units=total_unit_count,
                    occupied=capped,
                    vacant=vacant,
                    occupancy_rate=round(capped / total_unit_count, 3) if total_unit_count else 0,
                )
            )

        return OccupancyTrend(
            manager_id=manager_id,
            property_id=property_id,
            periods=trend_periods,
            period_count=len(trend_periods),
            direction=_compute_direction_inverse([p.occupancy_rate for p in trend_periods]),
        )

    async def rent_trend(
        self,
        manager_id: str | None = None,
        property_id: str | None = None,
        periods: int = 12,
    ) -> RentTrend:
        if property_id:
            properties = [await self._ps.get_property(property_id)]
            properties = [p for p in properties if p is not None]
        elif manager_id:
            properties = await self._ps.list_properties(manager_id=manager_id)
        else:
            properties = await self._ps.list_properties()

        all_leases = await asyncio.gather(
            *[self._ps.list_leases(property_id=p.id) for p in properties]
        )
        flat_leases = [le for lease_list in all_leases for le in lease_list]

        by_month: dict[str, list[float]] = {}
        for le in flat_leases:
            ts = le.last_confirmed_at or le.first_seen_at
            if ts is None or le.status.value not in ("active",):
                continue
            key = ts.strftime("%Y-%m")
            by_month.setdefault(key, []).append(float(le.monthly_rent))

        sorted_months = sorted(by_month.keys())[-periods:]
        trend_periods: list[RentTrendPeriod] = []
        for month in sorted_months:
            rents = sorted(by_month[month])
            total = sum(rents)
            count = len(rents)
            median = rents[count // 2] if count else 0.0
            trend_periods.append(
                RentTrendPeriod(
                    period=month,
                    avg_rent=round(total / count, 2) if count else 0.0,
                    median_rent=round(median, 2),
                    total_rent=round(total, 2),
                    unit_count=count,
                )
            )

        return RentTrend(
            manager_id=manager_id,
            property_id=property_id,
            periods=trend_periods,
            period_count=len(trend_periods),
            direction=_compute_direction_inverse([p.avg_rent for p in trend_periods]),
        )

    async def maintenance_trend(
        self,
        manager_id: str | None = None,
        property_id: str | None = None,
        unit_id: str | None = None,
        periods: int = 12,
    ) -> MaintenanceTrend:
        requests = await self._ps.list_maintenance_requests(
            property_id=property_id,
            unit_id=unit_id,
            manager_id=manager_id,
        )

        opened_by_month: dict[str, list] = {}
        completed_by_month: dict[str, list] = {}
        for r in requests:
            open_key = r.created_at.strftime("%Y-%m")
            opened_by_month.setdefault(open_key, []).append(r)
            if r.completed_date:
                close_key = r.completed_date.strftime("%Y-%m")
                completed_by_month.setdefault(close_key, []).append(r)

        all_months = sorted(set(opened_by_month) | set(completed_by_month))[-periods:]

        trend_periods: list[MaintenanceTrendPeriod] = []
        for month in all_months:
            opened = opened_by_month.get(month, [])
            completed = completed_by_month.get(month, [])

            resolution_days: list[float] = []
            total_cost = sum(float(r.cost) for r in completed if r.cost)
            for r in completed:
                if r.completed_date and r.created_at:
                    delta = (r.completed_date - r.created_at.date()).days
                    if delta >= 0:
                        resolution_days.append(float(delta))

            by_category: dict[str, int] = {}
            for r in opened:
                cat = r.category.value
                by_category[cat] = by_category.get(cat, 0) + 1

            trend_periods.append(
                MaintenanceTrendPeriod(
                    period=month,
                    opened=len(opened),
                    completed=len(completed),
                    net_open=len(opened) - len(completed),
                    total_cost=round(total_cost, 2),
                    avg_resolution_days=(
                        round(sum(resolution_days) / len(resolution_days), 1)
                        if resolution_days
                        else None
                    ),
                    by_category=by_category,
                )
            )

        return MaintenanceTrend(
            manager_id=manager_id,
            property_id=property_id,
            unit_id=unit_id,
            periods=trend_periods,
            period_count=len(trend_periods),
            direction=_compute_direction([float(p.opened) for p in trend_periods]),
        )
