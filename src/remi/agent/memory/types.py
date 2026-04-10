"""Memory types — the data model for agent memory.

``MemoryEntry`` is the unit of storage.  ``MemoryNamespace`` defines
the four logical partitions.  Entries carry optional ``entity_ids``
and ``tags`` for retrieval filtering — an agent writing a correction
about a specific property should tag it so future queries about that
property surface the correction.

``Importance`` controls retention.  Routine observations decay after
14 days, notable findings persist for 90 days, and critical learnings
never expire.

``RecallService`` is the port for pre-run memory recall. The concrete
``MemoryRecallService`` implements it.
"""

import abc
from datetime import datetime
from enum import IntEnum, StrEnum, unique

from pydantic import BaseModel, Field


@unique
class MemoryNamespace(StrEnum):
    """Logical partitions for agent memory.

    Agents specify a namespace when reading or writing so the memory
    store can apply different retention policies and retrieval strategies
    per partition.

    - ``episodic``  — what happened (session summaries, observations)
    - ``feedback``  — user corrections and mistakes to avoid
    - ``reference`` — curated knowledge, stable facts
    - ``plan``      — current objectives and approach (working memory)
    """

    EPISODIC = "episodic"
    FEEDBACK = "feedback"
    REFERENCE = "reference"
    PLAN = "plan"


@unique
class Importance(IntEnum):
    """Memory importance — controls retention TTL and recall ranking."""

    ROUTINE = 1
    NOTABLE = 2
    CRITICAL = 3


IMPORTANCE_TTL: dict[Importance, int | None] = {
    Importance.ROUTINE: 14 * 86400,
    Importance.NOTABLE: 90 * 86400,
    Importance.CRITICAL: None,
}


class MemoryEntry(BaseModel, frozen=True):
    """A single unit of agent memory."""

    namespace: str
    key: str
    value: str
    importance: int = Importance.ROUTINE
    score: float = 0.0
    created_at: datetime | None = None
    entity_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    source: str = ""
    metadata: dict[str, str] = Field(default_factory=dict)


class RecallService(abc.ABC):
    """Port for pre-run memory recall — retrieves and ranks memories.

    The concrete ``MemoryRecallService`` implements this.  ``RunDeps``
    should depend on this protocol, not the concrete class.
    """

    @abc.abstractmethod
    async def recall(
        self,
        question: str | None = None,
        *,
        namespaces: list[str] | None = None,
        entity_ids: list[str] | None = None,
        tags: list[str] | None = None,
        limit: int = 15,
    ) -> list[MemoryEntry]: ...

    @abc.abstractmethod
    def render(self, entries: list[MemoryEntry]) -> str | None: ...
