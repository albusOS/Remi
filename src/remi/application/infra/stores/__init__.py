"""RE persistence adapters — in-memory, Postgres, rollups.

Public API::

    from remi.application.infra.stores import StoreSuite, build_store_suite
"""

from remi.application.infra.stores.events import InMemoryEventStore
from remi.application.infra.stores.factory import StoreSuite, build_store_suite
from remi.application.infra.stores.projecting import ProjectingPropertyStore

__all__ = [
    "InMemoryEventStore",
    "ProjectingPropertyStore",
    "StoreSuite",
    "build_store_suite",
]
