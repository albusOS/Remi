"""Operations tools — agent-callable query operations for the operations slice."""

from __future__ import annotations

from typing import Any

import structlog

from remi.agent.types import ToolArg, ToolDefinition, ToolProvider, ToolRegistry

from .delinquency import DelinquencyResolver
from .leases import LeaseResolver
from .maintenance import MaintenanceResolver
from .vacancies import VacancyResolver

_log = structlog.get_logger(__name__)

_OPERATIONS = "delinquency, expiring_leases, vacancies, leases, maintenance"


class OperationsToolProvider(ToolProvider):
    """Registers the ``operations_query`` tool for operations slice queries."""

    def __init__(
        self,
        *,
        lease_resolver: LeaseResolver,
        maintenance_resolver: MaintenanceResolver,
        delinquency_resolver: DelinquencyResolver,
        vacancy_resolver: VacancyResolver,
    ) -> None:
        self._leases = lease_resolver
        self._maintenance = maintenance_resolver
        self._delinquency = delinquency_resolver
        self._vacancies = vacancy_resolver

    def register(self, registry: ToolRegistry) -> None:
        dispatch = {
            "delinquency": self._delinquency_op,
            "expiring_leases": self._expiring_leases_op,
            "vacancies": self._vacancies_op,
            "leases": self._leases_op,
            "maintenance": self._maintenance_op,
        }

        async def operations_query(args: dict[str, Any]) -> Any:
            operation = args.get("operation", "")
            if not operation:
                return {"error": "operation is required", "available": _OPERATIONS}
            handler = dispatch.get(operation)
            if handler is None:
                return {"error": f"Unknown operation: {operation!r}", "available": _OPERATIONS}
            try:
                return await handler(args)
            except Exception as exc:
                _log.warning("operations_query_error", operation=operation, exc_info=True)
                return {"error": f"{operation} failed: {exc}"}

        registry.register(
            "operations_query",
            operations_query,
            ToolDefinition(
                name="operations_query",
                description=(
                    "Operations data — delinquency, expiring leases, vacancies, "
                    "lease list, and maintenance. "
                    f"Operations: {_OPERATIONS}. "
                    "Use group_by='manager' with delinquency, expiring_leases, or vacancies "
                    "to get per-manager rollups instead of raw rows."
                ),
                args=[
                    ToolArg(name="operation", description=f"One of: {_OPERATIONS}", required=True),
                    ToolArg(name="manager_id", description="Filter / scope by manager ID"),
                    ToolArg(name="property_id", description="Filter by property ID (leases, maintenance)"),
                    ToolArg(name="days", description="Lookahead window for expiring_leases (default: 90)"),
                    ToolArg(name="status", description="Lease status filter for 'leases'"),
                    ToolArg(
                        name="group_by",
                        description=(
                            "Aggregate by dimension — use 'manager' with delinquency, "
                            "expiring_leases, or vacancies for per-manager rollups."
                        ),
                    ),
                ],
            ),
        )

    async def _delinquency_op(self, args: dict[str, Any]) -> dict[str, Any]:
        board = await self._delinquency.delinquency_board(manager_id=args.get("manager_id"))
        if args.get("group_by") == "manager":
            return _group_delinquency_by_manager(board)
        return board.model_dump(mode="json")

    async def _expiring_leases_op(self, args: dict[str, Any]) -> dict[str, Any]:
        days = int(args.get("days", "90"))
        cal = await self._leases.expiring_leases(days=days, manager_id=args.get("manager_id"))
        if args.get("group_by") == "manager":
            return _group_leases_by_manager(cal)
        return cal.model_dump(mode="json")

    async def _vacancies_op(self, args: dict[str, Any]) -> dict[str, Any]:
        tracker = await self._vacancies.vacancy_tracker(manager_id=args.get("manager_id"))
        if args.get("group_by") == "manager":
            return _group_vacancies_by_manager(tracker)
        return tracker.model_dump(mode="json")

    async def _leases_op(self, args: dict[str, Any]) -> dict[str, Any]:
        result = await self._leases.list_leases(
            property_id=args.get("property_id"),
            status=args.get("status"),
        )
        return result.model_dump(mode="json")

    async def _maintenance_op(self, args: dict[str, Any]) -> dict[str, Any]:
        result = await self._maintenance.list_maintenance(
            property_id=args.get("property_id"),
        )
        return result.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Group-by aggregations (deterministic, no LLM)
# ---------------------------------------------------------------------------


def _group_delinquency_by_manager(board: Any) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}
    for t in board.tenants:
        mid = t.manager_id or "unassigned"
        g = groups.setdefault(mid, {
            "manager_id": mid,
            "manager_name": t.manager_name or mid,
            "tenant_count": 0,
            "total_balance": 0.0,
            "balance_0_30": 0.0,
            "balance_30_plus": 0.0,
        })
        g["tenant_count"] += 1
        g["total_balance"] += t.balance_owed
        g["balance_0_30"] += t.balance_0_30
        g["balance_30_plus"] += t.balance_30_plus
    ranked = sorted(groups.values(), key=lambda g: g["total_balance"], reverse=True)
    return {
        "total_delinquent": board.total_delinquent,
        "total_balance": board.total_balance,
        "by_manager": ranked,
    }


def _group_leases_by_manager(cal: Any) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}
    for le in cal.leases:
        mid = le.manager_id or "unassigned"
        g = groups.setdefault(mid, {
            "manager_id": mid,
            "manager_name": le.manager_name or mid,
            "count": 0,
            "month_to_month": 0,
            "total_monthly_rent": 0.0,
        })
        g["count"] += 1
        if le.is_month_to_month:
            g["month_to_month"] += 1
        g["total_monthly_rent"] += le.monthly_rent
    ranked = sorted(groups.values(), key=lambda g: g["count"], reverse=True)
    return {
        "days_window": cal.days_window,
        "total_expiring": cal.total_expiring,
        "by_manager": ranked,
    }


def _group_vacancies_by_manager(tracker: Any) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}
    for u in tracker.units:
        mid = getattr(u, "manager_id", None) or "unassigned"
        mname = getattr(u, "manager_name", None) or mid
        g = groups.setdefault(mid, {
            "manager_id": mid,
            "manager_name": mname,
            "vacant_count": 0,
            "total_market_rent_at_risk": 0.0,
        })
        g["vacant_count"] += 1
        g["total_market_rent_at_risk"] += u.market_rent
    ranked = sorted(groups.values(), key=lambda g: g["vacant_count"], reverse=True)
    return {
        "total_vacant": tracker.total_vacant,
        "total_market_rent_at_risk": tracker.total_market_rent_at_risk,
        "by_manager": ranked,
    }
