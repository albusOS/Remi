"""Graph adapters — concrete store implementations.

- InMemoryMemoryStore: dev/test adapter for episodic memory
"""

from remi.agent.graph.adapters.mem import InMemoryMemoryStore

__all__ = [
    "InMemoryMemoryStore",
]
