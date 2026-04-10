"""Portfolio tools — agent-callable query operations for the portfolio slice."""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from remi.agent.types import ToolArg, ToolDefinition, ToolProvider, ToolRegistry
from remi.application.core.protocols import PropertyStore

from .dashboard import DashboardBuilder
from .managers import ManagerResolver
from .properties import PropertyResolver
from .rent_roll import RentRollResolver

_log = structlog.get_logger(__name__)

_OPERATIONS = "dashboard, managers, manager_review, properties, rent_roll, rankings"


class PortfolioToolProvider(ToolProvider):
    """Registers the ``portfolio_query`` tool for portfolio slice operations."""

    def __init__(
        self,
        *,
        manager_resolver: ManagerResolver,
        property_resolver: PropertyResolver,
        rent_roll_resolver: RentRollResolver,
        dashboard_builder: DashboardBuilder,
        property_store: PropertyStore,
    ) -> None:
        self._managers = manager_resolver
        self._properties = property_resolver
        self._rent_roll = rent_roll_resolver
        self._dashboard = dashboard_builder
        self._store = property_store

    def register(self, registry: ToolRegistry) -> None:
        dispatch = {
            "dashboard": self._dashboard_op,
            "managers": self._managers_op,
            "manager_review": self._manager_review_op,
            "properties": self._properties_op,
            "rent_roll": self._rent_roll_op,
            "rankings": self._rankings_op,
        }

        async def portfolio_query(args: dict[str, Any]) -> Any:
            operation = args.get("operation", "")
            if not operation:
                return {"error": "operation is required", "available": _OPERATIONS}
            handler = dispatch.get(operation)
            if handler is None:
                return {"error": f"Unknown operation: {operation!r}", "available": _OPERATIONS}
            try:
                return await handler(args)
            except Exception as exc:
                _log.warning("portfolio_query_error", operation=operation, exc_info=True)
                return {"error": f"{operation} failed: {exc}"}

        registry.register(
            "portfolio_query",
            portfolio_query,
            ToolDefinition(
                name="portfolio_query",
                description=(
                    "Portfolio data — managers, properties, rent rolls, rankings, "
                    "and the portfolio-wide dashboard overview. "
                    f"Operations: {_OPERATIONS}."
                ),
                args=[
                    ToolArg(name="operation", description=f"One of: {_OPERATIONS}", required=True),
                    ToolArg(name="manager_id", description="Filter by manager ID"),
                    ToolArg(name="property_id", description="Filter by property ID (rent_roll)"),
                    ToolArg(
                        name="sort_by",
                        description="Sort field for 'rankings' (default: delinquency_rate)",
                    ),
                ],
            ),
        )

    async def _dashboard_op(self, args: dict[str, Any]) -> dict[str, Any]:
        overview = await self._dashboard.dashboard_overview()
        return overview.model_dump(mode="json")

    async def _managers_op(self, args: dict[str, Any]) -> dict[str, Any]:
        summaries = await self._managers.list_manager_summaries()
        return {"managers": [s.model_dump(mode="json") for s in summaries]}

    async def _manager_review_op(self, args: dict[str, Any]) -> dict[str, Any]:
        mid = args.get("manager_id")
        if not mid:
            return {"error": "manager_id is required for manager_review"}

        summary = await self._managers.aggregate_manager(mid)
        if not summary:
            return {"error": f"Manager '{mid}' not found"}

        result: dict[str, Any] = {"summary": summary.model_dump(mode="json")}

        tasks: list[Any] = []
        keys: list[str] = []

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

        return result

    async def _properties_op(self, args: dict[str, Any]) -> dict[str, Any]:
        items = await self._properties.list_properties(manager_id=args.get("manager_id"))
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
        rows = await self._managers.rank_managers(sort_by=sort_by)
        return {"rankings": [r.model_dump(mode="json") for r in rows]}
