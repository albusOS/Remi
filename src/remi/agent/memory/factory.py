"""Memory store factory — backend selection based on settings."""

from __future__ import annotations

import importlib

from pydantic import BaseModel

from remi.agent.memory.mem import InMemoryMemoryStore
from remi.agent.memory.store import MemoryStore


class MemoryStoreSettings(BaseModel):
    """Episodic memory backend — ``memory`` or ``postgres``."""

    backend: str = "memory"

_ADAPTERS: dict[str, tuple[str, str]] = {
    "postgres": ("remi.agent.memory.adapters.pg", "PostgresMemoryStore"),
}


def build_memory_store(
    settings: MemoryStoreSettings,
    *,
    dsn: str = "",
) -> MemoryStore:
    """Return a MemoryStore for the configured backend.

    Supports ``memory`` and ``postgres``.  When ``postgres``, pass
    the database URL via *dsn*.
    """
    backend = settings.backend
    if backend == "memory":
        return InMemoryMemoryStore()

    if backend not in _ADAPTERS:
        raise ValueError(f"Unknown memory.backend: {backend!r}")

    if backend == "postgres":
        if not dsn:
            raise ValueError(
                "memory.backend is 'postgres' but no DATABASE_URL or state_store.dsn is configured."
            )
        from remi.agent.db.engine import async_session_factory, create_async_engine_from_url

        module_path, class_name = _ADAPTERS[backend]
        mod = importlib.import_module(module_path)
        store_cls = getattr(mod, class_name)

        engine = create_async_engine_from_url(dsn)
        return store_cls(async_session_factory(engine))

    raise ValueError(f"Unknown memory.backend: {backend!r}")
