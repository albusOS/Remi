"""Knowledge store and memory store factories — backend selection based on settings."""

from __future__ import annotations

from remi.agent.graph.adapters.mem import InMemoryKnowledgeStore, InMemoryMemoryStore
from remi.agent.graph.stores import KnowledgeStore, MemoryStore
from remi.types.config import RemiSettings


def build_knowledge_store(settings: RemiSettings) -> KnowledgeStore:
    """Return a KnowledgeStore for the configured backend.

    Supports ``memory`` and ``postgres``.
    """
    backend = settings.knowledge.backend
    if backend == "memory":
        return InMemoryKnowledgeStore()

    if backend == "postgres":
        dsn = settings.state_store.dsn or settings.secrets.database_url
        if not dsn:
            raise ValueError(
                "knowledge.backend is 'postgres' but no DATABASE_URL or "
                "state_store.dsn is configured."
            )
        from remi.agent.db.engine import async_session_factory, create_async_engine_from_url
        from remi.agent.graph.adapters.pg import PostgresKnowledgeStore

        engine = create_async_engine_from_url(dsn)
        return PostgresKnowledgeStore(async_session_factory(engine))

    raise ValueError(f"Unknown knowledge.backend: {backend!r}")


def build_memory_store(settings: RemiSettings) -> MemoryStore:
    """Return an episodic MemoryStore for the configured backend.

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
        from remi.agent.graph.adapters.pg_memory import PostgresMemoryStore

        engine = create_async_engine_from_url(dsn)
        return PostgresMemoryStore(async_session_factory(engine))

    raise ValueError(f"Unknown memory.backend: {backend!r}")
