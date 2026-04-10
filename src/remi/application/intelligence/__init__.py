"""Intelligence — search, trends, assertions, analytics.

Resolvers:
    SearchService          Hybrid keyword + semantic search
    TrendResolver          Cross-slice time-series analytics

Mutations:
    assert_fact            Record a user-asserted fact
    add_context            Attach user context to an entity

Read models:
    SearchHit / SearchApiResponse
    TrendPeriod, DelinquencyTrend, OccupancyTrend, RentTrend, MaintenanceTrend

API routers are imported directly by the shell via ``capabilities.py``
string references — they are NOT re-exported here to avoid barrel→api
→dependencies circular imports.
"""

from remi.application.intelligence.assertions import add_context, assert_fact
from remi.application.intelligence.search import SearchService
from remi.application.intelligence.trends import TrendResolver
from remi.application.intelligence.views import (
    DelinquencyTrend,
    MaintenanceTrend,
    OccupancyTrend,
    RentTrend,
    SearchApiResponse,
    SearchHit,
    TrendPeriod,
)

__all__ = [
    "DelinquencyTrend",
    "MaintenanceTrend",
    "OccupancyTrend",
    "RentTrend",
    "SearchApiResponse",
    "SearchHit",
    "SearchService",
    "TrendPeriod",
    "TrendResolver",
    "add_context",
    "assert_fact",
]
