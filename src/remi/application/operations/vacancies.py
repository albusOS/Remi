"""Operations — vacant and notice units with market rent at risk."""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal

from remi.application.core.models import LeaseStatus
from remi.application.core.protocols import PropertyStore
from remi.application.core.rules import derive_occupancy_status
from remi.application.portfolio.properties import property_ids_for_manager

from .views import VacancyTracker, VacantUnit


class VacancyResolver:
    """Vacant and notice units with market rent at risk."""

    def __init__(self, property_store: PropertyStore) -> None:
        self._ps = property_store

    async def vacancy_tracker(
        self,
        manager_id: str | None = None,
        property_ids: set[str] | None = None,
    ) -> VacancyTracker:
        all_units = await self._ps.list_units()

        allowed: set[str] | None = property_ids
        if allowed is None and manager_id:
            allowed = await property_ids_for_manager(self._ps, manager_id)
        if allowed is not None:
            all_units = [u for u in all_units if u.property_id in allowed]

        if not all_units:
            return VacancyTracker(
                total_vacant=0,
                total_notice=0,
                total_market_rent_at_risk=0.0,
                avg_days_vacant=None,
                units=[],
            )

        prop_ids_set = {u.property_id for u in all_units}
        all_lease_lists = await asyncio.gather(
            *[self._ps.list_leases(property_id=pid) for pid in prop_ids_set]
        )
        leases_by_unit: dict[str, list] = {}
        for lease_list in all_lease_lists:
            for le in lease_list:
                leases_by_unit.setdefault(le.unit_id, []).append(le)

        today = date.today()
        filtered_units = []
        notice_count = 0
        total_risk = Decimal("0")
        days_list: list[int] = []

        for u in all_units:
            unit_leases = leases_by_unit.get(u.id, [])
            occ_status = derive_occupancy_status(unit_leases)

            is_unit_vacant = occ_status.value in ("vacant_rented", "vacant_unrented")
            is_notice = occ_status.value in ("notice_rented", "notice_unrented")

            if not (is_unit_vacant or is_notice):
                continue
            if is_notice:
                notice_count += 1
            total_risk += u.market_rent

            ended = [
                le
                for le in unit_leases
                if le.status in (LeaseStatus.EXPIRED, LeaseStatus.TERMINATED)
            ]
            if ended:
                latest_end = max(le.end_date for le in ended)
                days_vacant = (today - latest_end).days
                if days_vacant >= 0:
                    days_list.append(days_vacant)
            else:
                days_vacant = None

            filtered_units.append((u, occ_status, days_vacant))

        unique_prop_ids = list({u.property_id for u, _, _ in filtered_units})
        props = await asyncio.gather(*[self._ps.get_property(pid) for pid in unique_prop_ids])
        prop_map = {pid: p for pid, p in zip(unique_prop_ids, props, strict=True) if p}

        mgr_ids = list({p.manager_id for p in prop_map.values() if p.manager_id})
        mgr_res = await asyncio.gather(*[self._ps.get_manager(mid) for mid in mgr_ids])
        mgr_map = {mid: m for mid, m in zip(mgr_ids, mgr_res, strict=True) if m}

        vacant_units: list[VacantUnit] = []
        for u, occ_status, days_vacant in filtered_units:
            prop = prop_map.get(u.property_id)
            mgr_id = prop.manager_id if prop else None
            mgr = mgr_map.get(mgr_id) if mgr_id else None
            vacant_units.append(
                VacantUnit(
                    unit_id=u.id,
                    unit_number=u.unit_number,
                    property_id=u.property_id,
                    property_name=prop.name if prop else u.property_id,
                    manager_id=mgr_id,
                    manager_name=mgr.name if mgr else None,
                    occupancy_status=occ_status.value,
                    days_vacant=days_vacant,
                    market_rent=float(u.market_rent),
                )
            )

        vacant_units.sort(key=lambda v: v.days_vacant or 0, reverse=True)

        return VacancyTracker(
            total_vacant=sum(
                1
                for v in vacant_units
                if v.occupancy_status not in ("notice_rented", "notice_unrented")
            ),
            total_notice=notice_count,
            total_market_rent_at_risk=float(total_risk),
            avg_days_vacant=round(sum(days_list) / len(days_list), 1) if days_list else None,
            units=vacant_units,
        )
