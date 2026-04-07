"""EventBus protocol and in-memory implementation.

The bus is general-purpose infrastructure — not tied to domain events.
Topic namespaces (``domain.*``, ``agent.*``, ``ui.*``) determine the
logical channel; the bus itself is agnostic.
"""

from __future__ import annotations

import abc
import asyncio
import fnmatch
from collections import defaultdict
from collections.abc import Awaitable, Callable

import structlog

from remi.agent.events.envelope import DomainEvent

logger = structlog.get_logger(__name__)

Subscriber = Callable[[DomainEvent], Awaitable[None]]


class EventBus(abc.ABC):
    """Async topic-based pub-sub — the OS-level event nervous system.

    Producers call ``publish``; subscribers register via ``subscribe``
    with a topic pattern (exact or glob, e.g. ``"agent.*"``).
    The bus carries domain events, agent lifecycle events, and UI
    telemetry — distinguished by topic namespace, not by bus instance.
    """

    @abc.abstractmethod
    async def publish(self, event: DomainEvent) -> None:
        """Emit an event to all matching subscribers."""

    @abc.abstractmethod
    def subscribe(self, pattern: str, handler: Subscriber) -> Callable[[], None]:
        """Register a handler for events matching ``pattern``.

        Returns an unsubscribe callable.
        """

    @abc.abstractmethod
    def subscriber_count(self, pattern: str | None = None) -> int:
        """Number of active subscriptions (optionally filtered by pattern)."""


class InMemoryEventBus(EventBus):
    """Simple in-process event bus — good for single-process deployments.

    Subscribers are invoked concurrently via ``asyncio.gather``.
    A failing subscriber is logged but does not block other subscribers
    or the publisher.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Subscriber]] = defaultdict(list)

    async def publish(self, event: DomainEvent) -> None:
        handlers = self._matching_handlers(event.topic)
        if not handlers:
            return
        results = await asyncio.gather(
            *(self._safe_call(h, event) for h in handlers),
            return_exceptions=True,
        )
        for i, result in enumerate(results):
            if isinstance(result, BaseException):
                logger.warning(
                    "event_subscriber_error",
                    topic=event.topic,
                    handler=handlers[i].__qualname__,
                    exc_info=result,
                )

    def subscribe(self, pattern: str, handler: Subscriber) -> Callable[[], None]:
        self._subscribers[pattern].append(handler)

        def _unsub() -> None:
            handlers = self._subscribers.get(pattern, [])
            if handler in handlers:
                handlers.remove(handler)
                if not handlers:
                    del self._subscribers[pattern]

        return _unsub

    def subscriber_count(self, pattern: str | None = None) -> int:
        if pattern is not None:
            return len(self._subscribers.get(pattern, []))
        return sum(len(v) for v in self._subscribers.values())

    def _matching_handlers(self, topic: str) -> list[Subscriber]:
        matched: list[Subscriber] = []
        for pattern, handlers in self._subscribers.items():
            if pattern == topic or fnmatch.fnmatch(topic, pattern):
                matched.extend(handlers)
        return matched

    @staticmethod
    async def _safe_call(handler: Subscriber, event: DomainEvent) -> None:
        await handler(event)
