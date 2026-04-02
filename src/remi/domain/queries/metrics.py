"""Backward-compat re-exports — canonical rules now live in portfolio/rules.py.

# COMPAT: remove once all importers switch to ``remi.domain.portfolio.rules``.
"""

from remi.domain.portfolio.rules import (  # noqa: F401
    BELOW_MARKET_THRESHOLD,
    is_below_market,
    is_maintenance_open,
    is_occupied,
    is_vacant,
    loss_to_lease,
    pct_below_market,
)

__all__ = [
    "BELOW_MARKET_THRESHOLD",
    "is_below_market",
    "is_maintenance_open",
    "is_occupied",
    "is_vacant",
    "loss_to_lease",
    "pct_below_market",
]
