"""Graph store ABCs — MemoryStore and WorldModel.

``WorldModel`` is the agent's read-only view of whatever domain world
it's operating in. The kernel never knows what entity types exist — it
discovers structure through ``schema()`` and traverses through
``get_links()``. The application layer provides the implementation.

DTOs (Entity, Relationship, etc.) live in ``remi.agent.graph.types``.
"""

from __future__ import annotations

import abc

from remi.agent.graph.types import (
    GraphLink,
    GraphObject,
    KnowledgeLink,
    MemoryEntry,
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


class MemoryStore(abc.ABC):
    """Key-value memory store for agent episodic memory."""

    @abc.abstractmethod
    async def store(
        self, namespace: str, key: str, value: str, *, ttl: int | None = None
    ) -> None: ...

    @abc.abstractmethod
    async def recall(self, namespace: str, key: str) -> str | None: ...

    @abc.abstractmethod
    async def search(self, namespace: str, query: str, *, limit: int = 5) -> list[MemoryEntry]: ...

    @abc.abstractmethod
    async def list_keys(self, namespace: str) -> list[str]: ...
