"""Cursor-based event buffer — stores recent events for polling retrieval.

An in-memory ring buffer of events published to the ``EventBus``.
Frontends poll ``GET /events?after=cursor`` and receive all events
since that cursor.  The buffer is bounded (oldest events are evicted
once the cap is reached), so clients that fall far behind lose events —
identical to a dropped WebSocket connection, but recoverable by
resetting the cursor.

The buffer is channel-agnostic: it stores whatever the bus delivers.
Channel-scoped retention (e.g. shorter TTL for ``ui.*`` vs. durable
``domain.*``) is a future extension point — the protocol stays the same.

Concurrency model: single-writer (the ``EventBus`` subscriber), multiple
readers (one per polling HTTP request).  The ``asyncio.Lock`` serializes
writes; reads take a snapshot under the lock and return immediately.
"""

from __future__ import annotations

import abc
import asyncio
from collections import deque
from dataclasses import dataclass

from remi.agent.events.envelope import DomainEvent


@dataclass(frozen=True, slots=True)
class BufferedEvent:
    """An event with its monotonic sequence number (the "cursor")."""

    seq: int
    event: DomainEvent


class EventBuffer(abc.ABC):
    """Bounded event log with cursor-based reads.

    Implementations store recent domain events and expose them via
    monotonic sequence cursors.  ``read_after(cursor)`` returns events
    newer than the cursor; ``append`` assigns the next cursor value.

    The in-memory implementation (``InMemoryEventBuffer``) uses a
    ``collections.deque`` ring buffer.  A Redis Streams implementation
    can replace it without changing consumers.
    """

    @property
    @abc.abstractmethod
    def latest_seq(self) -> int: ...

    @abc.abstractmethod
    async def append(self, event: DomainEvent) -> int:
        """Store an event and return its sequence number."""

    @abc.abstractmethod
    async def read_after(
        self,
        after: int,
        limit: int = 100,
    ) -> list[BufferedEvent]:
        """Return up to ``limit`` events with seq > ``after``."""

    @abc.abstractmethod
    async def wait_for_events(self, after: int, timeout: float = 0) -> bool:
        """Wait until new events exist beyond ``after``, or timeout."""

    @property
    @abc.abstractmethod
    def size(self) -> int: ...

    @property
    @abc.abstractmethod
    def capacity(self) -> int: ...


class InMemoryEventBuffer(EventBuffer):
    """Bounded in-memory ring buffer implementation of ``EventBuffer``."""

    def __init__(self, capacity: int = 4096) -> None:
        self._capacity = capacity
        self._buf: deque[BufferedEvent] = deque(maxlen=capacity)
        self._seq: int = 0
        self._lock = asyncio.Lock()
        self._notify: asyncio.Event = asyncio.Event()

    @property
    def latest_seq(self) -> int:
        return self._seq

    async def append(self, event: DomainEvent) -> int:
        async with self._lock:
            self._seq += 1
            self._buf.append(BufferedEvent(seq=self._seq, event=event))
            self._notify.set()
            return self._seq

    async def read_after(
        self,
        after: int,
        limit: int = 100,
    ) -> list[BufferedEvent]:
        async with self._lock:
            snapshot = list(self._buf)

        result: list[BufferedEvent] = []
        for entry in snapshot:
            if entry.seq > after:
                result.append(entry)
                if len(result) >= limit:
                    break
        return result

    async def wait_for_events(self, after: int, timeout: float = 0) -> bool:
        if self._seq > after:
            return True
        if timeout <= 0:
            return False
        self._notify.clear()
        try:
            await asyncio.wait_for(self._notify.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass
        return self._seq > after

    @property
    def size(self) -> int:
        return len(self._buf)

    @property
    def capacity(self) -> int:
        return self._capacity
