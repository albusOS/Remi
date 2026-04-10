"""Vector store factory — backend selection based on settings."""

from __future__ import annotations

import importlib

from remi.agent.vectors.types import VectorStoreSettings
from remi.agent.vectors.store import InMemoryVectorStore
from remi.agent.vectors.types import VectorStore

_ADAPTERS: dict[str, tuple[str, str]] = {
    "postgres": ("remi.agent.vectors.adapters.pg", "PostgresVectorStore"),
}


def build_vector_store(
    settings: VectorStoreSettings,
    *,
    dsn: str = "",
) -> VectorStore:
    """Return a VectorStore for the configured backend.

    Supports ``memory`` and ``postgres``.  When ``postgres``, pass
    the database URL via *dsn*.
    """
    backend = settings.backend
    if backend == "memory":
        return InMemoryVectorStore()

    adapter = _ADAPTERS.get(backend)
    if adapter is not None:
        if backend == "postgres" and not dsn:
            raise ValueError(
                "vectors.backend is 'postgres' but no DATABASE_URL or "
                "state_store.dsn is configured."
            )
        module_path, class_name = adapter
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)

        from remi.agent.db.engine import async_session_factory, create_async_engine_from_url

        engine = create_async_engine_from_url(dsn)
        return cls(async_session_factory(engine))

    raise ValueError(f"Unknown vectors.backend: {backend!r}")
