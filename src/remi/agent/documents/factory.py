"""Document store factory — selects and constructs the ContentStore backend.

The container calls ``build_content_store(backend, **kwargs)`` — it does not
inline backend selection or construction logic.

Supported backends
------------------
memory  (default)
    In-memory dict store. Fast, ephemeral, good for dev/test.

postgres
    Postgres-backed via SQLModel async sessions. Requires a
    ``session_factory`` kwarg (``async_sessionmaker[AsyncSession]``).
"""

from __future__ import annotations

import importlib
from typing import Any

import structlog

from remi.agent.documents.adapters.mem import InMemoryContentStore
from remi.agent.documents.types import ContentStore

_log = structlog.get_logger(__name__)

_ADAPTERS: dict[str, tuple[str, str]] = {
    "postgres": ("remi.agent.documents.adapters.pg", "PostgresContentStore"),
}


def build_content_store(backend: str = "memory", **kwargs: Any) -> ContentStore:
    """Construct the ContentStore backend selected by *backend*.

    Parameters
    ----------
    backend:
        ``"memory"`` (default) or ``"postgres"``.
    **kwargs:
        Backend-specific arguments (e.g. ``session_factory`` for postgres).
    """
    backend = backend.lower()

    if backend in ("memory", "in_memory"):
        _log.info("content_store_backend", backend="memory")
        return InMemoryContentStore()

    adapter = _ADAPTERS.get(backend)
    if adapter is None:
        raise ValueError(
            f"Unknown content store backend: {backend!r}. "
            f"Supported: memory, {', '.join(sorted(_ADAPTERS))}"
        )

    module_path, class_name = adapter
    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)
    _log.info("content_store_backend", backend=backend)
    return cls(**kwargs)
