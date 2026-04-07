"""MemoryStore protocol — the agent's read/write interface to memory.

Two primary operations:

- **write** — the agent decides something is worth remembering
- **read**  — the agent queries for relevant memories

Plus key-level recall and housekeeping.  The protocol is deliberately
simple so it can be backed by a dict (dev), Postgres (prod), or
eventually a vector-augmented store without changing callers.
"""

from __future__ import annotations

import abc

from remi.agent.memory.types import MemoryEntry


class MemoryStore(abc.ABC):
    """Read/write memory for agents — the OS-level persistence primitive."""

    @abc.abstractmethod
    async def write(
        self,
        namespace: str,
        key: str,
        value: str,
        *,
        importance: int = 1,
        entity_ids: list[str] | None = None,
        tags: list[str] | None = None,
        source: str = "",
        ttl: int | None = None,
    ) -> None:
        """Persist a memory entry.  Upserts on (namespace, key).

        ``importance`` (1=routine, 2=notable, 3=critical) influences
        both retention TTL and recall ranking.  When ``ttl`` is None
        the store may derive it from ``importance``.
        """

    @abc.abstractmethod
    async def read(
        self,
        namespace: str,
        query: str,
        *,
        entity_ids: list[str] | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        """Search memory by text query, optionally filtered by entity or tag.

        Returns entries ranked by relevance (implementation-defined).
        """

    @abc.abstractmethod
    async def recall(self, namespace: str, key: str) -> str | None:
        """Exact key lookup — returns the value or None."""

    @abc.abstractmethod
    async def list_keys(self, namespace: str) -> list[str]:
        """List all keys in a namespace."""

    @abc.abstractmethod
    async def delete(self, namespace: str, key: str) -> bool:
        """Remove a single entry.  Returns True if it existed."""
