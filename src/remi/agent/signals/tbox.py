"""Domain schema — lightweight structural vocabulary parsed from domain.yaml.

DomainSchema holds entity type definitions, relationship definitions, and
business process definitions.  It describes what exists in the domain and
how things connect — not what to look for or what thresholds matter.

The agent discovers patterns and calculates significance from the actual data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class EntityTypeDef(BaseModel, frozen=True):
    """An entity type in the domain — a noun the agent can reason about."""

    name: str
    description: str = ""
    key_fields: list[str] = Field(default_factory=list)


class RelationshipDef(BaseModel, frozen=True):
    """A typed, directed relationship between two entity types."""

    name: str
    source: str
    target: str
    description: str = ""


class ProcessDef(BaseModel, frozen=True):
    """A business process — a lifecycle the domain operates."""

    name: str
    description: str = ""
    involves: list[str] = Field(default_factory=list)


class DomainSchema(BaseModel, frozen=True):
    """Structural vocabulary of the domain, parsed from domain.yaml.

    Describes what entity types exist, how they relate, and what business
    processes the product covers.  Validated at startup — a malformed
    domain.yaml fails fast with a Pydantic error.
    """

    entity_types: list[EntityTypeDef] = Field(default_factory=list)
    relationships: list[RelationshipDef] = Field(default_factory=list)
    processes: list[ProcessDef] = Field(default_factory=list)

    @classmethod
    def from_yaml(cls, raw: dict[str, Any]) -> DomainSchema:
        schema = raw.get("schema", {})

        entity_types = [EntityTypeDef(**et) for et in schema.get("entity_types", [])]
        relationships = [RelationshipDef(**r) for r in schema.get("relationships", [])]
        processes = [ProcessDef(**p) for p in schema.get("processes", [])]

        return cls(
            entity_types=entity_types,
            relationships=relationships,
            processes=processes,
        )

    def entity_type(self, name: str) -> EntityTypeDef | None:
        """Look up an entity type by name."""
        for et in self.entity_types:
            if et.name == name:
                return et
        return None

    def entity_type_names(self) -> list[str]:
        return [et.name for et in self.entity_types]

    def relationships_for(self, entity_name: str) -> list[RelationshipDef]:
        """Return relationships where entity_name is source or target."""
        return [r for r in self.relationships if r.source == entity_name or r.target == entity_name]

    def processes_involving(self, entity_name: str) -> list[ProcessDef]:
        """Return processes that involve a given entity type."""
        return [p for p in self.processes if entity_name in p.involves]


# Keep the old name as an alias during transition
DomainTBox = DomainSchema
MutableTBox = DomainSchema


def load_domain_yaml(path: Path) -> dict[str, Any]:
    """Load domain.yaml and return the raw parsed dict.

    Use ``DomainSchema.from_yaml(raw)`` to get a typed schema.
    """
    import yaml

    if not path.exists():
        return {}
    with open(path) as fh:
        data: dict[str, Any] = yaml.safe_load(fh) or {}
    return data
