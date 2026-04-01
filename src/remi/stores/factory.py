"""Store factory functions — backend selection based on settings.

Postgres-related imports are conditional since ``sqlmodel`` / ``asyncpg``
are optional dependencies (``remi[postgres]``).
"""

from __future__ import annotations

from typing import Any

from remi.config.settings import RemiSettings
from remi.models.documents import DocumentStore
from remi.models.properties import PropertyStore
from remi.models.rollups import RollupStore
from remi.stores.documents import InMemoryDocumentStore
from remi.stores.rollups import InMemoryRollupStore, PostgresRollupStore


def build_property_store(
    settings: RemiSettings,
) -> tuple[PropertyStore, Any, Any]:
    """Return ``(property_store, db_engine | None, session_factory | None)``.

    The engine and session factory are exposed so the container can share
    them with other Postgres-backed stores and the bootstrap lifecycle.
    """
    from remi.stores.properties import InMemoryPropertyStore

    backend = settings.state_store.backend
    if backend == "postgres":
        dsn = settings.state_store.dsn or settings.secrets.database_url
        if not dsn:
            raise ValueError(
                "state_store.backend is 'postgres' but no DATABASE_URL or "
                "state_store.dsn is configured."
            )
        from remi.db.engine import async_session_factory, create_async_engine_from_url
        from remi.stores.postgres import PostgresPropertyStore

        engine = create_async_engine_from_url(dsn)
        session_factory = async_session_factory(engine)
        return PostgresPropertyStore(session_factory), engine, session_factory

    return InMemoryPropertyStore(), None, None


def build_document_store(session_factory: Any | None) -> DocumentStore:
    """Return a Postgres or in-memory document store."""
    if session_factory is not None:
        from remi.stores.postgres_documents import PostgresDocumentStore

        return PostgresDocumentStore(session_factory)
    return InMemoryDocumentStore()


def build_rollup_store(session_factory: Any | None) -> RollupStore:
    """Return a Postgres or in-memory rollup store."""
    if session_factory is not None:
        return PostgresRollupStore(session_factory)
    return InMemoryRollupStore()
