"""Graph package — knowledge graph types, ABCs, and persistence.

Public imports::

    from remi.agent.graph import KnowledgeGraph, Entity, GraphObject, ...
"""

from remi.agent.graph.adapters.bridge import BridgedKnowledgeGraph, CoreTypeBindings
from remi.agent.graph.factory import build_knowledge_store, build_memory_store
from remi.agent.graph.projector import GraphProjector
from remi.agent.graph.stores import (
    KnowledgeGraph,
    KnowledgeStore,
    MemoryStore,
    Ontology,
)
from remi.agent.graph.types import (
    ActionDef,
    AggregateResult,
    Entity,
    FactProvenance,
    FKProjection,
    GraphLink,
    GraphObject,
    KnowledgeLink,
    KnowledgeProvenance,
    LinkTypeDef,
    MemoryEntry,
    ObjectTypeDef,
    ProjectionMapping,
    PropertyDef,
    Relationship,
    TimelineEvent,
)

__all__ = [
    "ActionDef",
    "AggregateResult",
    "BridgedKnowledgeGraph",
    "CoreTypeBindings",
    "Entity",
    "FactProvenance",
    "FKProjection",
    "GraphLink",
    "GraphObject",
    "GraphProjector",
    "KnowledgeGraph",
    "KnowledgeLink",
    "KnowledgeProvenance",
    "KnowledgeStore",
    "LinkTypeDef",
    "MemoryEntry",
    "MemoryStore",
    "ObjectTypeDef",
    "Ontology",
    "ProjectionMapping",
    "PropertyDef",
    "Relationship",
    "TimelineEvent",
    "build_knowledge_store",
    "build_memory_store",
]
