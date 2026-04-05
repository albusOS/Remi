"""Vector store factory — backend selection based on settings."""

from __future__ import annotations

from remi.agent.vectors.store import InMemoryVectorStore
from remi.agent.vectors.types import VectorStore
from remi.types.config import RemiSettings


def build_vector_store(settings: RemiSettings) -> VectorStore:
    """Return a VectorStore for the configured backend.

    Supports ``memory`` and ``postgres``.
    """
    backend = settings.vectors.backend
    if backend == "memory":
        return InMemoryVectorStore()

    if backend == "postgres":
        dsn = settings.state_store.dsn or settings.secrets.database_url
        if not dsn:
            raise ValueError(
                "vectors.backend is 'postgres' but no DATABASE_URL or "
                "state_store.dsn is configured."
            )
        from remi.agent.db.engine import async_session_factory, create_async_engine_from_url
        from remi.agent.vectors.pg import PostgresVectorStore

        engine = create_async_engine_from_url(dsn)
        return PostgresVectorStore(async_session_factory(engine))

    raise ValueError(f"Unknown vectors.backend: {backend!r}")
