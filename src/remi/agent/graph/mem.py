"""In-memory EntityStore implementation."""

from __future__ import annotations

from typing import Any

from remi.agent.graph.stores import EntityStore
from remi.agent.graph.types import GraphLink, GraphObject


class InMemoryEntityStore(EntityStore):
    """Dict-backed schema-free entity+link store."""

    def __init__(self) -> None:
        self._entities: dict[str, GraphObject] = {}
        self._links: list[GraphLink] = []

    async def put_entity(
        self,
        id: str,
        type_name: str,
        properties: dict[str, Any],
    ) -> None:
        existing = self._entities.get(id)
        if existing is not None:
            merged = {**existing.properties, **properties}
            self._entities[id] = GraphObject(
                id=id,
                type_name=type_name,
                properties=merged,
            )
        else:
            self._entities[id] = GraphObject(
                id=id,
                type_name=type_name,
                properties=dict(properties),
            )

    async def put_link(
        self,
        source_id: str,
        target_id: str,
        relation: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        for i, link in enumerate(self._links):
            if (
                link.source_id == source_id
                and link.target_id == target_id
                and link.link_type == relation
            ):
                merged = {**link.properties, **(properties or {})}
                self._links[i] = GraphLink(
                    source_id=source_id,
                    target_id=target_id,
                    link_type=relation,
                    properties=merged,
                )
                return
        self._links.append(
            GraphLink(
                source_id=source_id,
                target_id=target_id,
                link_type=relation,
                properties=properties or {},
            )
        )

    async def get_entity(self, id: str) -> GraphObject | None:
        return self._entities.get(id)

    async def find_entities(
        self,
        query: str,
        *,
        type_name: str | None = None,
        limit: int = 20,
    ) -> list[GraphObject]:
        q = query.lower()
        results: list[GraphObject] = []
        for entity in self._entities.values():
            if type_name and entity.type_name != type_name:
                continue
            if self._matches(entity, q):
                results.append(entity)
                if len(results) >= limit:
                    break
        return results

    async def get_links(
        self,
        entity_id: str,
        *,
        direction: str = "both",
        relation: str | None = None,
    ) -> list[GraphLink]:
        results: list[GraphLink] = []
        for link in self._links:
            if relation and link.link_type != relation:
                continue
            is_source = link.source_id == entity_id
            is_target = link.target_id == entity_id
            if direction == "outgoing" and is_source:
                results.append(link)
            elif direction == "incoming" and is_target:
                results.append(link)
            elif direction == "both" and (is_source or is_target):
                results.append(link)
        return results

    @staticmethod
    def _matches(entity: GraphObject, query: str) -> bool:
        if query in entity.id.lower():
            return True
        if query in entity.type_name.lower():
            return True
        for val in entity.properties.values():
            if query in str(val).lower():
                return True
        return False
