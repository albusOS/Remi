"""Memory store factory — backend selection based on settings."""

from __future__ import annotations

from remi.agent.memory.mem import InMemoryMemoryStore
from remi.agent.memory.store import MemoryStore
from remi.types.config import RemiSettings


def build_memory_store(settings: RemiSettings) -> MemoryStore:
    """Return a MemoryStore for the configured backend.

    Supports ``memory`` and ``postgres``.
    """
    backend = settings.memory.backend
    if backend == "memory":
        return InMemoryMemoryStore()

    if backend == "postgres":
        dsn = settings.state_store.dsn or settings.secrets.database_url
        if not dsn:
            raise ValueError(
                "memory.backend is 'postgres' but no DATABASE_URL or "
                "state_store.dsn is configured."
            )
        from remi.agent.db.engine import async_session_factory, create_async_engine_from_url
        from remi.agent.memory.pg import PostgresMemoryStore

        engine = create_async_engine_from_url(dsn)
        return PostgresMemoryStore(async_session_factory(engine))

    raise ValueError(f"Unknown memory.backend: {backend!r}")
