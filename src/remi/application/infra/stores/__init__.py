"""RE persistence adapters — in-memory and Postgres.

Public API::

    from remi.application.infra.stores import StoreSuite, build_store_suite
"""

from remi.application.infra.stores.events import InMemoryEventStore
from remi.application.infra.stores.factory import StoreSuite, build_store_suite

__all__ = [
    "InMemoryEventStore",
    "StoreSuite",
    "build_store_suite",
]
