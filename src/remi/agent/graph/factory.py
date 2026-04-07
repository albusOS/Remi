"""Graph store factories — backend selection based on settings."""

from __future__ import annotations

from remi.agent.graph.mem import InMemoryEntityStore
from remi.agent.graph.stores import EntityStore


def build_entity_store() -> EntityStore:
    """Return a schema-free EntityStore (in-memory for now)."""
    return InMemoryEntityStore()
