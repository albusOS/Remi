"""In-memory implementation of MemoryStore."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from remi.agent.graph.stores import MemoryStore
from remi.agent.graph.types import MemoryEntry


class InMemoryMemoryStore(MemoryStore):
    """Dict-backed key-value memory for development and testing."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, MemoryEntry]] = defaultdict(dict)

    async def store(self, namespace: str, key: str, value: str, *, ttl: int | None = None) -> None:
        self._data[namespace][key] = MemoryEntry(
            namespace=namespace,
            key=key,
            value=value,
            created_at=datetime.now(UTC),
        )

    async def recall(self, namespace: str, key: str) -> str | None:
        entry = self._data.get(namespace, {}).get(key)
        return entry.value if entry else None

    async def search(self, namespace: str, query: str, *, limit: int = 5) -> list[MemoryEntry]:
        entries = list(self._data.get(namespace, {}).values())
        query_lower = query.lower()
        scored = []
        for entry in entries:
            val_str = entry.value.lower()
            key_str = entry.key.lower()
            if query_lower in val_str or query_lower in key_str:
                scored.append(entry)
        return scored[:limit]

    async def list_keys(self, namespace: str) -> list[str]:
        return list(self._data.get(namespace, {}).keys())
