"""Group-by aggregators for query operations — deterministic in-process, no LLM.

Each function collapses a flat result model into a per-dimension rollup sorted
by the most operationally relevant metric (balance, count, or vacancy).
They are pure transforms: no I/O, no side effects.
"""

from __future__ import annotations

from typing import Any


def group_delinquency_by_property(board: Any) -> dict[str, Any]:
    """Aggregate a DelinquencyBoard into a per-property rollup.

    Returns ``by_property`` sorted by ``total_balance`` descending so the
    worst offenders appear first.  Each entry carries both aging buckets
    (0-30 days, 30+ days) and the owning manager for cross-filtering.
    """
    groups: dict[str, dict[str, Any]] = {}
    for t in board.tenants:
        pid = t.property_id or "unassigned"
        g = groups.setdefault(pid, {
            "property_id": pid,
            "property_name": t.property_name or pid,
            "manager_id": t.manager_id,
            "manager_name": t.manager_name,
            "tenant_count": 0,
            "total_balance": 0.0,
            "balance_0_30": 0.0,
            "balance_30_plus": 0.0,
        })
        g["tenant_count"] += 1
        g["total_balance"] += t.balance_owed
        g["balance_0_30"] += t.balance_0_30
        g["balance_30_plus"] += t.balance_30_plus
    return {
        "total_delinquent": board.total_delinquent,
        "total_balance": board.total_balance,
        "by_property": sorted(
            groups.values(), key=lambda g: g["total_balance"], reverse=True
        ),
    }


def group_delinquency_by_manager(board: Any) -> dict[str, Any]:
    """Aggregate a DelinquencyBoard into a per-manager rollup.

    Returns ``by_manager`` sorted by ``total_balance`` descending.
    """
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
    return {
        "total_delinquent": board.total_delinquent,
        "total_balance": board.total_balance,
        "by_manager": sorted(groups.values(), key=lambda g: g["total_balance"], reverse=True),
    }


def group_leases_by_manager(cal: Any) -> dict[str, Any]:
    """Aggregate a LeaseCalendar into a per-manager rollup.

    Returns ``by_manager`` sorted by lease ``count`` descending.
    """
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
    return {
        "days_window": cal.days_window,
        "total_expiring": cal.total_expiring,
        "by_manager": sorted(groups.values(), key=lambda g: g["count"], reverse=True),
    }


def group_vacancies_by_manager(tracker: Any) -> dict[str, Any]:
    """Aggregate a VacancyTracker into a per-manager rollup.

    Returns ``by_manager`` sorted by ``vacant_count`` descending.
    """
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
    return {
        "total_vacant": tracker.total_vacant,
        "total_market_rent_at_risk": tracker.total_market_rent_at_risk,
        "by_manager": sorted(groups.values(), key=lambda g: g["vacant_count"], reverse=True),
    }
