"""QueryToolProvider — single ``query`` tool with in-process resolver dispatch.

One tool, one ``operation`` parameter, ~300 tokens of schema. The LLM
picks the operation; the tool fetches data in-process via resolvers and
returns structured JSON. No subprocess, no sandbox, sub-10ms data access.

Operations: dashboard, managers, manager_review, properties, rent_roll,
rankings, delinquency, expiring_leases, vacancies, leases, maintenance,
search.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from remi.agent.types import ToolArg, ToolDefinition, ToolProvider, ToolRegistry
from remi.application.core.protocols import PropertyStore
from remi.application.intelligence import DashboardResolver, SearchService
from remi.application.operations import LeaseResolver, MaintenanceResolver
from remi.application.portfolio import ManagerResolver, PropertyResolver, RentRollResolver

logger = structlog.get_logger(__name__)

_OPERATIONS = (
    "dashboard, managers, manager_review, properties, rent_roll, "
    "rankings, delinquency, expiring_leases, vacancies, leases, "
    "maintenance, search"
)


class QueryToolProvider(ToolProvider):
    """Registers a single ``query`` tool that dispatches to resolvers."""

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

    def register(self, registry: ToolRegistry) -> None:
        dispatch = self._build_dispatch()

        async def query(args: dict[str, Any]) -> Any:
            operation = args.get("operation", "")
            if not operation:
                return {"error": "operation is required", "available": _OPERATIONS}
            handler = dispatch.get(operation)
            if handler is None:
                return {"error": f"Unknown operation: {operation}", "available": _OPERATIONS}
            try:
                return await handler(args)
            except Exception as exc:
                logger.warning(
                    "query_tool_error",
                    operation=operation,
                    exc_info=True,
                )
                return {"error": f"{operation} failed: {exc}"}

        registry.register(
            "query",
            query,
            ToolDefinition(
                name="query",
                description=(
                    "Fast in-process data lookup. Returns structured JSON for any "
                    "portfolio, operations, or intelligence query. Use this for "
                    "dashboards, manager reviews, property lists, lease data, "
                    "delinquency, vacancies, maintenance, and entity search."
                ),
                args=[
                    ToolArg(
                        name="operation",
                        description=f"One of: {_OPERATIONS}",
                        required=True,
                    ),
                    ToolArg(
                        name="manager_id",
                        description="Filter by manager ID (most operations)",
                    ),
                    ToolArg(
                        name="property_id",
                        description="Filter by property ID (properties, rent_roll, leases, maintenance)",
                    ),
                    ToolArg(
                        name="query",
                        description="Search text (for 'search' operation)",
                    ),
                    ToolArg(
                        name="sort_by",
                        description="Sort field (for 'rankings' — default: delinquency_rate)",
                    ),
                    ToolArg(
                        name="days",
                        description="Lookahead window (for 'expiring_leases' — default: 90)",
                    ),
                    ToolArg(
                        name="status",
                        description="Lease status filter (for 'leases')",
                    ),
                ],
            ),
        )

    def _build_dispatch(self) -> dict[str, Any]:
        return {
            "dashboard": self._dashboard_op,
            "managers": self._managers_op,
            "manager_review": self._manager_review_op,
            "properties": self._properties_op,
            "rent_roll": self._rent_roll_op,
            "rankings": self._rankings_op,
            "delinquency": self._delinquency_op,
            "expiring_leases": self._expiring_leases_op,
            "vacancies": self._vacancies_op,
            "leases": self._leases_op,
            "maintenance": self._maintenance_op,
            "search": self._search_op,
        }

    async def _dashboard_op(self, args: dict[str, Any]) -> dict[str, Any]:
        overview = await self._dashboard.dashboard_overview()
        return overview.model_dump(mode="json")

    async def _managers_op(self, args: dict[str, Any]) -> dict[str, Any]:
        summaries = await self._manager.list_manager_summaries()
        return {"managers": [s.model_dump(mode="json") for s in summaries]}

    async def _manager_review_op(self, args: dict[str, Any]) -> dict[str, Any]:
        mid = args.get("manager_id")
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

    async def _properties_op(self, args: dict[str, Any]) -> dict[str, Any]:
        items = await self._property.list_properties(manager_id=args.get("manager_id"))
        return {"properties": [p.model_dump(mode="json") for p in items]}

    async def _rent_roll_op(self, args: dict[str, Any]) -> dict[str, Any]:
        pid = args.get("property_id")
        if not pid:
            return {"error": "property_id is required for rent_roll"}
        result = await self._rent_roll.build_rent_roll(pid)
        if not result:
            return {"error": f"Property '{pid}' not found"}
        return result.model_dump(mode="json")

    async def _rankings_op(self, args: dict[str, Any]) -> dict[str, Any]:
        sort_by = args.get("sort_by", "delinquency_rate")
        rows = await self._manager.rank_managers(sort_by=sort_by)
        return {"rankings": [r.model_dump(mode="json") for r in rows]}

    async def _delinquency_op(self, args: dict[str, Any]) -> dict[str, Any]:
        board = await self._dashboard.delinquency_board(manager_id=args.get("manager_id"))
        return board.model_dump(mode="json")

    async def _expiring_leases_op(self, args: dict[str, Any]) -> dict[str, Any]:
        days = int(args.get("days", "90"))
        cal = await self._dashboard.lease_expiration_calendar(
            days=days, manager_id=args.get("manager_id"),
        )
        return cal.model_dump(mode="json")

    async def _vacancies_op(self, args: dict[str, Any]) -> dict[str, Any]:
        tracker = await self._dashboard.vacancy_tracker(manager_id=args.get("manager_id"))
        return tracker.model_dump(mode="json")

    async def _leases_op(self, args: dict[str, Any]) -> dict[str, Any]:
        result = await self._lease.list_leases(
            property_id=args.get("property_id"),
            status=args.get("status"),
        )
        return result.model_dump(mode="json")

    async def _maintenance_op(self, args: dict[str, Any]) -> dict[str, Any]:
        result = await self._maintenance.list_maintenance(
            property_id=args.get("property_id"),
        )
        return result.model_dump(mode="json")

    async def _search_op(self, args: dict[str, Any]) -> dict[str, Any]:
        q = args.get("query", "")
        if not q:
            return {"error": "query is required for search"}
        results = await self._search.search(q)
        return {"results": [r.model_dump(mode="json") for r in results]}
