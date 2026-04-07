"""RE persistence adapters — in-memory and Postgres.

Public API::

    from remi.application.infra.stores import StoreSuite, build_store_suite
"""

from remi.application.infra.stores.events import InMemoryEventStore
from remi.application.infra.stores.factory import StoreSuite, build_store_suite
from remi.application.infra.stores.projecting import (
    ProjectingPropertyStore,
    wrap_property_store_with_projection,
)

__all__ = [
    "InMemoryEventStore",
    "ProjectingPropertyStore",
    "StoreSuite",
    "build_store_suite",
    "wrap_property_store_with_projection",
]
