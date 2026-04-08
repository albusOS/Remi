"""QueryDispatcher — in-process data resolution for the query fast path.

Implements the ``DataResolver`` protocol from ``agent/runtime/query_path.py``.
Maps operation names to resolver methods and returns serialized Pydantic
models.  This is the single place where operation → resolver wiring lives.

Not a tool.  Not registered on any tool catalog.  Called directly by the
router's query path.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from remi.application.core.protocols import PropertyStore
from remi.application.intelligence import DashboardResolver, SearchService
from remi.application.operations import LeaseResolver, MaintenanceResolver
from remi.application.portfolio import ManagerResolver, PropertyResolver, RentRollResolver

logger = structlog.get_logger(__name__)


class QueryDispatcher:
    """Maps operation names to resolver calls.  Returns dicts ready for LLM context."""

    def __init__(
        self,
        *,
        manager_resolver: ManagerResolver,
        property_resolver: PropertyResolver,
        rent_roll_resolver: RentRollResolver,
        dashboard_resolver: DashboardResolver,
        lease_resolver: LeaseResolver,
        maintenance_resolver: MaintenanceResolver,
        search_service: SearchService,
        property_store: PropertyStore,
    ) -> None:
        self._manager = manager_resolver
        self._property = property_resolver
        self._rent_roll = rent_roll_resolver
        self._dashboard = dashboard_resolver
        self._lease = lease_resolver
        self._maintenance = maintenance_resolver
        self._search = search_service
        self._store = property_store

    async def resolve(self, operation: str, params: dict[str, str]) -> dict[str, Any]:
        """Dispatch to the right resolver.  Returns serializable dict."""
        handler = _DISPATCH.get(operation)
        if handler is None:
            return {"error": f"Unknown operation: {operation}"}
        return await handler(self, params)

    # -- Operation handlers ------------------------------------------------

    async def _managers(self, params: dict[str, str]) -> dict[str, Any]:
        summaries = await self._manager.list_manager_summaries()
        return {"managers": [s.model_dump(mode="json") for s in summaries]}

    async def _manager_review(self, params: dict[str, str]) -> dict[str, Any]:
        mid = params.get("manager_id")
        if not mid:
            return {"error": "manager_id is required for manager_review"}

        summary = await self._manager.aggregate_manager(mid)
        if not summary:
            return {"error": f"Manager '{mid}' not found"}

        result: dict[str, Any] = {"summary": summary.model_dump(mode="json")}

        tasks: list[Any] = []
        keys: list[str] = []

        if summary.total_delinquent_balance > 0:
            tasks.append(self._dashboard.delinquency_board(manager_id=mid))
            keys.append("delinquency")

        if summary.metrics.expiring_leases_90d > 0:
            tasks.append(self._dashboard.lease_expiration_calendar(days=90, manager_id=mid))
            keys.append("lease_expirations")

        if summary.metrics.vacant > 0:
            tasks.append(self._dashboard.vacancy_tracker(manager_id=mid))
            keys.append("vacancies")

        tasks.append(self._store.list_action_items(manager_id=mid))
        keys.append("_action_items")
        tasks.append(self._store.list_notes(entity_type="PropertyManager", entity_id=mid))
        keys.append("_notes")

        gathered = await asyncio.gather(*tasks)
        for key, val in zip(keys, gathered, strict=True):
            if key == "_action_items" and val:
                result["action_items"] = [ai.model_dump(mode="json") for ai in val]
            elif key == "_notes" and val:
                result["notes"] = [n.model_dump(mode="json") for n in val]
            elif key.startswith("_"):
                continue
            elif val is not None:
                result[key] = val.model_dump(mode="json")

        return result

    async def _properties(self, params: dict[str, str]) -> dict[str, Any]:
        items = await self._property.list_properties(manager_id=params.get("manager_id"))
        return {"properties": [p.model_dump(mode="json") for p in items]}

    async def _rent_roll(self, params: dict[str, str]) -> dict[str, Any]:
        pid = params.get("property_id")
        if not pid:
            return {"error": "property_id is required for rent_roll"}
        result = await self._rent_roll.build_rent_roll(pid)
        if not result:
            return {"error": f"Property '{pid}' not found"}
        return result.model_dump(mode="json")

    async def _rankings(self, params: dict[str, str]) -> dict[str, Any]:
        sort_by = params.get("sort_by", "delinquency_rate")
        rows = await self._manager.rank_managers(sort_by=sort_by)
        return {"rankings": [r.model_dump(mode="json") for r in rows]}

    async def _dashboard(self, params: dict[str, str]) -> dict[str, Any]:
        overview = await self._dashboard.dashboard_overview()
        return overview.model_dump(mode="json")

    async def _delinquency(self, params: dict[str, str]) -> dict[str, Any]:
        board = await self._dashboard.delinquency_board(manager_id=params.get("manager_id"))
        return board.model_dump(mode="json")

    async def _expiring_leases(self, params: dict[str, str]) -> dict[str, Any]:
        days = int(params.get("days", "90"))
        cal = await self._dashboard.lease_expiration_calendar(
            days=days, manager_id=params.get("manager_id"),
        )
        return cal.model_dump(mode="json")

    async def _vacancies(self, params: dict[str, str]) -> dict[str, Any]:
        tracker = await self._dashboard.vacancy_tracker(manager_id=params.get("manager_id"))
        return tracker.model_dump(mode="json")

    async def _leases(self, params: dict[str, str]) -> dict[str, Any]:
        result = await self._lease.list_leases(
            property_id=params.get("property_id"),
            status=params.get("status"),
        )
        return result.model_dump(mode="json")

    async def _maintenance(self, params: dict[str, str]) -> dict[str, Any]:
        result = await self._maintenance.list_maintenance(
            property_id=params.get("property_id"),
        )
        return result.model_dump(mode="json")

    async def _search(self, params: dict[str, str]) -> dict[str, Any]:
        query = params.get("query", "")
        if not query:
            return {"error": "query is required for search"}
        results = await self._search.search(query)
        return {"results": [r.model_dump(mode="json") for r in results]}


_DISPATCH: dict[str, Any] = {
    "managers": QueryDispatcher._managers,
    "manager_review": QueryDispatcher._manager_review,
    "properties": QueryDispatcher._properties,
    "rent_roll": QueryDispatcher._rent_roll,
    "rankings": QueryDispatcher._rankings,
    "dashboard": QueryDispatcher._dashboard,
    "delinquency": QueryDispatcher._delinquency,
    "expiring_leases": QueryDispatcher._expiring_leases,
    "vacancies": QueryDispatcher._vacancies,
    "leases": QueryDispatcher._leases,
    "maintenance": QueryDispatcher._maintenance,
    "search": QueryDispatcher._search,
}
