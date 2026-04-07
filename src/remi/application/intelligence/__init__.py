"""Intelligence — dashboard, search, ontology, knowledge, events.

Queries:
    DashboardResolver      Five typed dashboard views over PropertyStore
    SearchService          Hybrid keyword + semantic search

API:
    dashboard_router       /dashboard views and trends
    search_router          /search typeahead
    knowledge_router       /knowledge assert + context
    events_router          /events change history
    ontology_router        /ontology schema + graph + snapshot
"""

from pathlib import Path

from .api import dashboard_router, events_router, knowledge_router, ontology_router, search_router
from .queries import DashboardResolver, SearchService

MANIFEST_PATH = Path(__file__).parent / "app.yaml"

__all__ = [
    "DashboardResolver",
    "MANIFEST_PATH",
    "SearchService",
    "dashboard_router",
    "events_router",
    "knowledge_router",
    "ontology_router",
    "search_router",
]
