"""SnapshotService — captures and retrieves PM performance snapshots.

After each document upload, a snapshot of every active PM's key metrics
is recorded with a timestamp.  The frontend uses these to show trends
(week-over-week occupancy, revenue, delinquency, etc.).

Both manager-level and property-level snapshots are produced in each
``capture()`` walk and persisted via the injected ``SnapshotStore``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel

from remi.models.properties import OccupancyStatus, PropertyStore, UnitStatus

if TYPE_CHECKING:
    from remi.stores.snapshots import SnapshotStore


class ManagerSnapshot(BaseModel, frozen=True):
    manager_id: str
    manager_name: str
    timestamp: datetime
    property_count: int = 0
    total_units: int = 0
    occupied: int = 0
    vacant: int = 0
    occupancy_rate: float = 0.0
    total_rent: float = 0.0
    total_market_rent: float = 0.0
    loss_to_lease: float = 0.0
    delinquent_count: int = 0
    delinquent_balance: float = 0.0


class PropertySnapshot(BaseModel, frozen=True):
    property_id: str
    property_name: str
    manager_id: str
    manager_name: str
    timestamp: datetime
    total_units: int = 0
    occupied: int = 0
    vacant: int = 0
    occupancy_rate: float = 0.0
    total_rent: float = 0.0
    total_market_rent: float = 0.0
    loss_to_lease: float = 0.0
    maintenance_open: int = 0
    maintenance_closed: int = 0
    avg_maintenance_cost: float = 0.0


class SnapshotService:
    """Captures and stores PM and property performance snapshots."""

    def __init__(
        self,
        property_store: PropertyStore,
        snapshot_store: SnapshotStore | None = None,
    ) -> None:
        self._ps = property_store
        self._store = snapshot_store
        # In-memory caches (always kept in sync whether a store is present or not)
        self._snapshots: list[ManagerSnapshot] = []
        self._property_snapshots: list[PropertySnapshot] = []

    async def capture(self) -> list[ManagerSnapshot]:
        """Take a snapshot of all managers' current metrics.

        Produces both ``ManagerSnapshot`` and ``PropertySnapshot`` rows in a
        single portfolio walk. Both are persisted via the snapshot store (if
        configured) and kept in the in-memory cache.
        """
        now = datetime.now(UTC)
        managers = await self._ps.list_managers()
        manager_batch: list[ManagerSnapshot] = []
        property_batch: list[PropertySnapshot] = []

        for mgr in managers:
            portfolios = await self._ps.list_portfolios(manager_id=mgr.id)
            prop_count = 0
            total_u = 0
            occ = 0
            vac = 0
            rent = Decimal("0")
            market = Decimal("0")
            ltl = Decimal("0")

            for pf in portfolios:
                props = await self._ps.list_properties(portfolio_id=pf.id)
                prop_count += len(props)

                for prop in props:
                    units = await self._ps.list_units(property_id=prop.id)
                    p_occ = 0
                    p_vac = 0
                    p_rent = Decimal("0")
                    p_market = Decimal("0")
                    p_ltl = Decimal("0")

                    for u in units:
                        total_u += 1
                        if u.status == UnitStatus.OCCUPIED or (
                            u.occupancy_status == OccupancyStatus.OCCUPIED
                        ):
                            occ += 1
                            p_occ += 1
                        elif u.status == UnitStatus.VACANT or (
                            u.occupancy_status
                            and u.occupancy_status
                            in (OccupancyStatus.VACANT_RENTED, OccupancyStatus.VACANT_UNRENTED)
                        ):
                            vac += 1
                            p_vac += 1
                        rent += u.current_rent
                        market += u.market_rent
                        p_rent += u.current_rent
                        p_market += u.market_rent
                        if u.current_rent < u.market_rent:
                            diff = u.market_rent - u.current_rent
                            ltl += diff
                            p_ltl += diff

                    p_total = p_occ + p_vac
                    maint_requests = await self._ps.list_maintenance_requests(property_id=prop.id)
                    maint_open = sum(
                        1 for r in maint_requests
                        if str(r.status).lower() in ("open", "pending", "in_progress")
                    )
                    maint_closed = sum(
                        1 for r in maint_requests
                        if str(r.status).lower() in ("closed", "completed", "resolved")
                    )
                    costs = [float(r.cost) for r in maint_requests if r.cost and float(r.cost) > 0]
                    avg_cost = sum(costs) / len(costs) if costs else 0.0

                    property_batch.append(
                        PropertySnapshot(
                            property_id=prop.id,
                            property_name=prop.name,
                            manager_id=mgr.id,
                            manager_name=mgr.name,
                            timestamp=now,
                            total_units=len(units),
                            occupied=p_occ,
                            vacant=p_vac,
                            occupancy_rate=round(p_occ / p_total, 3) if p_total else 0.0,
                            total_rent=float(p_rent),
                            total_market_rent=float(p_market),
                            loss_to_lease=float(p_ltl),
                            maintenance_open=maint_open,
                            maintenance_closed=maint_closed,
                            avg_maintenance_cost=round(avg_cost, 2),
                        )
                    )

            del_count = 0
            del_balance = Decimal("0")
            tenants = await self._ps.list_tenants()
            allowed_pids: set[str] = set()
            for pf in portfolios:
                for p in await self._ps.list_properties(portfolio_id=pf.id):
                    allowed_pids.add(p.id)
            for t in tenants:
                if t.balance_owed <= 0:
                    continue
                leases = await self._ps.list_leases(tenant_id=t.id)
                if any(le.property_id in allowed_pids for le in leases):
                    del_count += 1
                    del_balance += t.balance_owed

            snap = ManagerSnapshot(
                manager_id=mgr.id,
                manager_name=mgr.name,
                timestamp=now,
                property_count=prop_count,
                total_units=total_u,
                occupied=occ,
                vacant=vac,
                occupancy_rate=round(occ / total_u, 3) if total_u else 0.0,
                total_rent=float(rent),
                total_market_rent=float(market),
                loss_to_lease=float(ltl),
                delinquent_count=del_count,
                delinquent_balance=float(del_balance),
            )
            manager_batch.append(snap)

        self._snapshots.extend(manager_batch)
        self._property_snapshots.extend(property_batch)

        if self._store is not None:
            self._store.append_manager_snapshots([s.model_dump() for s in manager_batch])
            self._store.append_property_snapshots([s.model_dump() for s in property_batch])

        return manager_batch

    # ------------------------------------------------------------------
    # Manager queries (kept for backward compat with dashboard endpoints)
    # ------------------------------------------------------------------

    def get_history(self, manager_id: str | None = None) -> list[ManagerSnapshot]:
        """Return stored manager snapshots, optionally filtered by manager."""
        if manager_id:
            return [s for s in self._snapshots if s.manager_id == manager_id]
        return list(self._snapshots)

    def latest(self, manager_id: str) -> ManagerSnapshot | None:
        """Most recent manager snapshot."""
        matching = [s for s in self._snapshots if s.manager_id == manager_id]
        return matching[-1] if matching else None

    def previous(self, manager_id: str) -> ManagerSnapshot | None:
        """Second-most-recent manager snapshot (for computing deltas)."""
        matching = [s for s in self._snapshots if s.manager_id == manager_id]
        return matching[-2] if len(matching) >= 2 else None

    # ------------------------------------------------------------------
    # Property queries
    # ------------------------------------------------------------------

    def get_property_history(
        self,
        property_id: str | None = None,
        manager_id: str | None = None,
    ) -> list[PropertySnapshot]:
        """Return stored property snapshots with optional filters."""
        rows = self._property_snapshots
        if property_id:
            rows = [s for s in rows if s.property_id == property_id]
        if manager_id:
            rows = [s for s in rows if s.manager_id == manager_id]
        return list(rows)
