"""In-memory MemoryStore — dict-backed, suitable for dev and testing."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from remi.agent.memory.store import MemoryStore
from remi.agent.memory.types import IMPORTANCE_TTL, Importance, MemoryEntry


class InMemoryMemoryStore(MemoryStore):
    """Dict-backed memory store with substring search.

    Results from ``read`` are ranked by importance (desc) then recency
    (desc) so the most critical and recent memories surface first.
    """

    def __init__(self) -> None:
        self._data: dict[str, dict[str, MemoryEntry]] = defaultdict(dict)

    async def write(
        self,
        namespace: str,
        key: str,
        value: str,
        *,
        importance: int = Importance.ROUTINE,
        entity_ids: list[str] | None = None,
        tags: list[str] | None = None,
        source: str = "",
        ttl: int | None = None,
    ) -> None:
        if ttl is None:
            imp = Importance(min(importance, Importance.CRITICAL))
            ttl = IMPORTANCE_TTL.get(imp)
        self._data[namespace][key] = MemoryEntry(
            namespace=namespace,
            key=key,
            value=value,
            importance=importance,
            created_at=datetime.now(UTC),
            entity_ids=entity_ids or [],
            tags=tags or [],
            source=source,
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
        entries = list(self._data.get(namespace, {}).values())
        query_lower = query.lower()
        matched: list[MemoryEntry] = []

        for entry in entries:
            if not self._matches(entry, query_lower, entity_ids, tags):
                continue
            matched.append(entry)

        matched.sort(key=_rank_key, reverse=True)
        return matched[:limit]

    async def recall(self, namespace: str, key: str) -> str | None:
        entry = self._data.get(namespace, {}).get(key)
        return entry.value if entry else None

    async def list_keys(self, namespace: str) -> list[str]:
        return list(self._data.get(namespace, {}).keys())

    async def delete(self, namespace: str, key: str) -> bool:
        ns = self._data.get(namespace, {})
        if key in ns:
            del ns[key]
            return True
        return False

    @staticmethod
    def _matches(
        entry: MemoryEntry,
        query_lower: str,
        entity_ids: list[str] | None,
        tags: list[str] | None,
    ) -> bool:
        if entity_ids:
            if not any(eid in entry.entity_ids for eid in entity_ids):
                return False

        if tags:
            if not any(t in entry.tags for t in tags):
                return False

        if query_lower:
            text = f"{entry.key} {entry.value}".lower()
            if query_lower not in text:
                return False

        return True


def _rank_key(entry: MemoryEntry) -> tuple[int, float]:
    ts = entry.created_at.timestamp() if entry.created_at else 0.0
    return (entry.importance, ts)
