"""Store factory functions — backend selection based on settings.

Callers receive a ``StoreSuite`` — no SQLAlchemy types in the public
interface.  Postgres-related imports are conditional since ``sqlmodel``
/ ``asyncpg`` are optional dependencies (``remi[postgres]``).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from remi.agent.documents import ContentStore
from remi.agent.documents.adapters.mem import InMemoryContentStore
from remi.application.core.protocols import PropertyStore


@dataclass
class _BootstrapHook:
    """Callable wrapper so StoreSuite doesn't expose engine types."""

    _fn: Callable[[], Awaitable[None]]

    async def __call__(self) -> None:
        await self._fn()


@dataclass
class StoreSuite:
    """All application-layer stores, ready to use.

    The Postgres branch holds an engine internally for bootstrap;
    non-Postgres backends don't need to expose SQLAlchemy types.
    """

    property_store: PropertyStore
    content_store: ContentStore
    _bootstrap: _BootstrapHook | None = None

    async def ensure_tables_created(self) -> None:
        """Create DB tables if backed by Postgres. No-op for in-memory."""
        if self._bootstrap is not None:
            await self._bootstrap()


def build_store_suite(
    *,
    backend: str = "in_memory",
    dsn: str = "",
) -> StoreSuite:
    """Build all application-layer stores from backend selection.

    Parameters
    ----------
    backend:
        ``"in_memory"`` (default) or ``"postgres"``.
    dsn:
        Database connection URL. Required when *backend* is ``"postgres"``.
    """
    from remi.application.stores.mem import InMemoryPropertyStore

    if backend == "postgres":
        if not dsn:
            raise ValueError(
                "state_store.backend is 'postgres' but no DATABASE_URL or "
                "state_store.dsn is configured."
            )
        from remi.agent.db.engine import (
            async_session_factory,
            create_async_engine_from_url,
            create_tables,
        )
        from remi.application.stores.pg import PostgresPropertyStore

        engine = create_async_engine_from_url(dsn)
        session_factory = async_session_factory(engine)

        from remi.agent.documents.adapters.pg import PostgresContentStore

        async def _bootstrap() -> None:
            await create_tables(engine)

        return StoreSuite(
            property_store=PostgresPropertyStore(session_factory),
            content_store=PostgresContentStore(session_factory),
            _bootstrap=_BootstrapHook(_bootstrap),
        )

    return StoreSuite(
        property_store=InMemoryPropertyStore(),
        content_store=InMemoryContentStore(),
    )
