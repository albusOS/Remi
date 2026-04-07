"""Agent memory — first-class read/write persistence for agents.

Memory is an OS-level primitive.  Agents explicitly decide what to
remember (``memory_write``) and what to recall (``memory_read``).
Four namespaces partition memory by lifecycle:

- ``episodic``  — what happened (session observations, findings)
- ``feedback``  — user corrections and mistakes to avoid
- ``reference`` — curated knowledge, stable facts
- ``plan``      — current objectives and working state

Post-run **episode extraction** uses a cheap LLM call to distill the
conversation into structured observations that are written back to the
store.  The **recall service** retrieves relevant memories ranked by
importance and recency, replacing the naive "list first 10 keys" pattern.

The ``MemoryStore`` protocol is backend-agnostic — in-memory for dev,
Postgres for production, vector-augmented when needed.

Public API::

    from remi.agent.memory import (
        MemoryStore, MemoryEntry, MemoryNamespace, Importance,
        InMemoryMemoryStore, build_memory_store,
        MemoryRecallService, extract_episode,
    )
"""

from remi.agent.memory.extraction import extract_episode
from remi.agent.memory.factory import build_memory_store
from remi.agent.memory.mem import InMemoryMemoryStore
from remi.agent.memory.recall import MemoryRecallService
from remi.agent.memory.store import MemoryStore
from remi.agent.memory.types import Importance, MemoryEntry, MemoryNamespace

__all__ = [
    "Importance",
    "InMemoryMemoryStore",
    "MemoryEntry",
    "MemoryNamespace",
    "MemoryRecallService",
    "MemoryStore",
    "build_memory_store",
    "extract_episode",
]
