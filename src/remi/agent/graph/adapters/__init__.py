"""Graph adapters — concrete KnowledgeGraph and KnowledgeStore implementations.

- BridgedKnowledgeGraph: routes to domain stores + KnowledgeStore
- InMemoryMemoryStore / InMemoryKnowledgeStore: dev/test adapters
"""

from remi.agent.graph.adapters.bridge import BridgedKnowledgeGraph, CoreTypeBindings
from remi.agent.graph.adapters.mem import InMemoryKnowledgeStore, InMemoryMemoryStore

__all__ = [
    "BridgedKnowledgeGraph",
    "CoreTypeBindings",
    "InMemoryKnowledgeStore",
    "InMemoryMemoryStore",
]
