"""Graph store ABCs — WorldModel and EntityStore.

``WorldModel`` is the agent's read-only view of whatever domain world
it's operating in. The kernel never knows what entity types exist — it
discovers structure through ``schema()`` and traverses through
``get_links()``. The application layer provides the implementation.

``EntityStore`` is a schema-free, writable node+edge store. The LLM
decides entity types, relation names, and property shapes at runtime
via tools. No validation, no dispatch table — just upsert and query.

DTOs (Entity, Relationship, etc.) live in ``remi.agent.graph.types``.

Note: ``MemoryStore`` has moved to ``remi.agent.memory``.
"""

from __future__ import annotations

import abc
from typing import Any

from remi.agent.graph.types import (
    GraphLink,
    GraphObject,
    KnowledgeLink,
    ObjectTypeDef,
)


class WorldModel(abc.ABC):
    """Read-only world model — the agent's perception of its domain.

    The agent kernel depends on this interface. The application layer
    implements it by wrapping its own stores (PropertyStore, etc.) and
    deriving links from FK fields. The kernel never imports domain types.
    """

    @abc.abstractmethod
    async def search_objects(
        self,
        query: str,
        *,
        object_type: str | None = None,
        limit: int = 20,
    ) -> list[GraphObject]:
        """Full-text / fuzzy search over world entities."""
        ...

    @abc.abstractmethod
    async def get_object(self, object_id: str) -> GraphObject | None:
        """Look up a single entity by ID."""
        ...

    @abc.abstractmethod
    async def get_links(
        self,
        object_id: str,
        *,
        direction: str = "both",
        link_type: str | None = None,
    ) -> list[GraphLink]:
        """Return edges connected to *object_id*.

        ``direction`` is ``"outgoing"``, ``"incoming"``, or ``"both"``.
        """
        ...

    @abc.abstractmethod
    async def schema(self) -> list[ObjectTypeDef]:
        """Return the type definitions known to this world."""
        ...


class EntityStore(abc.ABC):
    """Schema-free, writable node+edge store.

    The LLM decides what types and relations to create via tools.
    The store enforces nothing — it's a dumb persistence layer.
    """

    @abc.abstractmethod
    async def put_entity(
        self, id: str, type_name: str, properties: dict[str, Any],
    ) -> None:
        """Upsert a node. Merges properties on conflict."""
        ...

    @abc.abstractmethod
    async def put_link(
        self,
        source_id: str,
        target_id: str,
        relation: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Upsert a directed edge. Merges properties on conflict."""
        ...

    @abc.abstractmethod
    async def get_entity(self, id: str) -> GraphObject | None:
        """Look up a single entity by ID."""
        ...

    @abc.abstractmethod
    async def find_entities(
        self,
        query: str,
        *,
        type_name: str | None = None,
        limit: int = 20,
    ) -> list[GraphObject]:
        """Substring search over entity IDs, types, and property values."""
        ...

    @abc.abstractmethod
    async def get_links(
        self,
        entity_id: str,
        *,
        direction: str = "both",
        relation: str | None = None,
    ) -> list[GraphLink]:
        """Return edges connected to *entity_id*."""
        ...


