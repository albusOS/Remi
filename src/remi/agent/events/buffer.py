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

import asyncio
from collections import deque
from dataclasses import dataclass, field

from remi.agent.events.envelope import DomainEvent


@dataclass(frozen=True, slots=True)
class BufferedEvent:
    """An event with its monotonic sequence number (the "cursor")."""

    seq: int
    event: DomainEvent


class EventBuffer:
    """Bounded in-memory event log with cursor-based reads.

    ``append`` assigns a monotonic sequence number; ``read_after`` returns
    all events with ``seq > after``.  The caller's ``after`` value is the
    cursor — ``0`` means "everything currently in the buffer."
    """

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
        """Store an event and return its sequence number."""
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
        """Return up to ``limit`` events with seq > ``after``."""
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
        """Wait until new events exist beyond ``after``, or timeout.

        Returns True if events are available, False on timeout.
        Used for optional long-poll support.
        """
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
