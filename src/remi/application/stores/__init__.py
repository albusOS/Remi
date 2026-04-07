"""RE persistence — stores, world model, and indexer adapters.

Public API::

    from remi.application.stores import StoreSuite, build_store_suite
    from remi.application.stores import build_re_world_model
    from remi.application.stores import AgentTextIndexer, AgentVectorSearch
"""

from remi.application.stores.events import InMemoryEventStore
from remi.application.stores.factory import StoreSuite, build_store_suite
from remi.application.stores.indexer import AgentTextIndexer, AgentVectorSearch
from remi.application.stores.world import REWorldModel, build_re_world_model

__all__ = [
    "AgentTextIndexer",
    "AgentVectorSearch",
    "InMemoryEventStore",
    "REWorldModel",
    "StoreSuite",
    "build_re_world_model",
    "build_store_suite",
]
