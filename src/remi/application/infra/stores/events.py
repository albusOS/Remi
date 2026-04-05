"""In-memory EventStore implementation."""

from __future__ import annotations

from remi.application.core.events import ChangeSet, EventStore


class InMemoryEventStore(EventStore):
    def __init__(self) -> None:
        self._by_id: dict[str, ChangeSet] = {}
        self._ordered: list[ChangeSet] = []

    async def append(self, changeset: ChangeSet) -> None:
        self._by_id[changeset.id] = changeset
        self._ordered.append(changeset)

    async def get(self, changeset_id: str) -> ChangeSet | None:
        return self._by_id.get(changeset_id)

    async def list_by_entity(
        self,
        entity_id: str,
        *,
        limit: int = 50,
    ) -> list[ChangeSet]:
        results: list[ChangeSet] = []
        for cs in reversed(self._ordered):
            entity_ids = {e.entity_id for e in cs.events}
            if entity_id in entity_ids or entity_id in cs.unchanged_ids:
                results.append(cs)
                if len(results) >= limit:
                    break
        return results

    async def list_recent(self, *, limit: int = 20) -> list[ChangeSet]:
        return list(reversed(self._ordered[-limit:]))
