"""ScopedMemoryStore — workspace-isolated wrapper over any MemoryStore.

Prefixes all namespace keys with a workspace identifier so that multiple
workspaces sharing a single backend (Postgres, Redis) cannot collide.

For the default workspace (no prefix), delegates directly — zero overhead
for the single-tenant path.

Usage::

    from remi.agent.memory.scoped import ScopedMemoryStore

    base = InMemoryMemoryStore()
    scoped = ScopedMemoryStore(base, prefix="ws:maintenance-llc:")
    await scoped.write("episodic", "finding-1", "Plumber no-showed")
    # stored under namespace "ws:maintenance-llc:episodic"
"""

from __future__ import annotations

from remi.agent.memory.store import MemoryStore
from remi.agent.memory.types import MemoryEntry


class ScopedMemoryStore(MemoryStore):
    """Workspace-scoped delegation wrapper.

    Prefixes every namespace with ``prefix`` before forwarding to the
    underlying store. When ``prefix`` is empty, this is a transparent
    pass-through with no overhead.
    """

    def __init__(self, inner: MemoryStore, prefix: str = "") -> None:
        self._inner = inner
        self._prefix = prefix

    def _ns(self, namespace: str) -> str:
        if not self._prefix:
            return namespace
        return f"{self._prefix}{namespace}"

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
        await self._inner.write(
            self._ns(namespace),
            key,
            value,
            importance=importance,
            entity_ids=entity_ids,
            tags=tags,
            source=source,
            ttl=ttl,
        )

    async def read(
        self,
        namespace: str,
        query: str,
        *,
        entity_ids: list[str] | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        return await self._inner.read(
            self._ns(namespace),
            query,
            entity_ids=entity_ids,
            tags=tags,
            limit=limit,
        )

    async def recall(self, namespace: str, key: str) -> str | None:
        return await self._inner.recall(self._ns(namespace), key)

    async def list_keys(self, namespace: str) -> list[str]:
        return await self._inner.list_keys(self._ns(namespace))

    async def delete(self, namespace: str, key: str) -> bool:
        return await self._inner.delete(self._ns(namespace), key)
