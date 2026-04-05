"""Intelligence — signals, dashboard, search, ontology, knowledge, events.

Situation awareness and analytical capabilities: signal detection results,
director dashboard, semantic search, knowledge graph operations, and
change event observation.
"""

from remi.application.api.intelligence.dashboard import router as dashboard_router
from remi.application.api.intelligence.events import router as events_router
from remi.application.api.intelligence.knowledge import router as knowledge_router
from remi.application.api.intelligence.ontology import router as ontology_router
from remi.application.api.intelligence.search import router as search_router
from remi.application.api.intelligence.signals import router as signals_router

__all__ = [
    "dashboard_router",
    "events_router",
    "knowledge_router",
    "ontology_router",
    "search_router",
    "signals_router",
]
