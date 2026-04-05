"""Signal and feedback store factories — backend selection based on settings."""

from __future__ import annotations

from remi.agent.signals.persistence.mem import InMemoryFeedbackStore, InMemorySignalStore
from remi.agent.signals.persistence.stores import FeedbackStore, SignalStore
from remi.types.config import RemiSettings


def _get_signal_session_factory(settings: RemiSettings):  # noqa: ANN202
    """Lazy-build a shared session factory for Postgres signal stores."""
    dsn = settings.state_store.dsn or settings.secrets.database_url
    if not dsn:
        raise ValueError(
            "signals.backend is 'postgres' but no DATABASE_URL or "
            "state_store.dsn is configured."
        )
    from remi.agent.db.engine import async_session_factory, create_async_engine_from_url

    engine = create_async_engine_from_url(dsn)
    return async_session_factory(engine)


def build_signal_store(settings: RemiSettings) -> SignalStore:
    """Return a SignalStore for the configured backend.

    Supports ``memory`` and ``postgres``.
    """
    backend = settings.signals.backend
    if backend == "memory":
        return InMemorySignalStore()

    if backend == "postgres":
        from remi.agent.signals.persistence.pg import PostgresSignalStore

        return PostgresSignalStore(_get_signal_session_factory(settings))

    raise ValueError(f"Unknown signals.backend: {backend!r}")


def build_feedback_store(settings: RemiSettings) -> FeedbackStore:
    """Return a FeedbackStore for the configured backend.

    Supports ``memory`` and ``postgres``.
    """
    backend = settings.signals.backend
    if backend == "memory":
        return InMemoryFeedbackStore()

    if backend == "postgres":
        from remi.agent.signals.persistence.pg import PostgresFeedbackStore

        return PostgresFeedbackStore(_get_signal_session_factory(settings))

    raise ValueError(f"Unknown signals.backend: {backend!r}")
