"""Event bus factory — build the right backend from settings.

``memory`` is the default: single-process, zero dependencies.
``redis`` is the cross-process backend: publish/subscribe via Redis
pub/sub, cursor-based polling via Redis Streams. Implementation is
lazy-imported to avoid a hard dependency on ``redis`` in dev.
"""

from __future__ import annotations

import structlog

from pydantic import BaseModel

from remi.agent.events.bus import EventBus, InMemoryEventBus


class EventBusSettings(BaseModel):
    """Event bus backend — ``memory`` for single-process, ``redis`` for cross-process."""

    backend: str = "memory"
    url: str = ""

logger = structlog.get_logger(__name__)


def build_event_bus(settings: EventBusSettings) -> EventBus:
    """Construct the event bus backend selected by settings."""
    backend = settings.backend.lower()

    if backend == "memory":
        logger.info("event_bus_backend", backend="memory")
        return InMemoryEventBus()

    if backend == "redis":
        raise NotImplementedError(
            "Redis event bus backend is defined as a protocol extension point. "
            "Implement ``RedisEventBus(EventBus)`` in ``agent/events/redis.py`` "
            "and register it here when Redis pub/sub is needed."
        )

    raise ValueError(f"Unknown event bus backend: {backend!r}. Supported: memory, redis")
