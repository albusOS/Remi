"""ContextFrame — the agent's typed perception of its world.

The frame separates two concerns:

- **WorldState** (TBox shape): static domain knowledge — how many signal
  definitions, thresholds, policies, and causal chains the agent operates
  with.  This is set once at agent priming time and does not change per turn.

- **ContextFrame** (per-turn ABox): entities, graph neighborhood, and
  document context assembled by the ContextBuilder each turn.

Both stay typed until the injection boundary, where rendering projects
them into prose for the LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from remi.agent.graph.retrieval.retriever import ResolvedEntity
from remi.agent.graph.types import KnowledgeLink
from remi.agent.signals import CausalChain, DomainTBox, MutableTBox, Policy


@dataclass(frozen=True)
class WorldState:
    """Static TBox shape — the dimensions of the agent's domain knowledge.

    Computed once from DomainTBox at priming time.  Immutable for the
    lifetime of the agent session.
    """

    signal_definitions: int = 0
    thresholds: int = 0
    policies: int = 0
    causal_chains: int = 0
    compositions: int = 0

    @property
    def loaded(self) -> bool:
        return self.signal_definitions > 0

    @classmethod
    def from_tbox(cls, domain: DomainTBox | MutableTBox | None) -> WorldState:
        if domain is None:
            return cls()
        return cls(
            signal_definitions=len(getattr(domain, "signals", {})),
            thresholds=len(getattr(domain, "thresholds", {})),
            policies=len(getattr(domain, "policies", [])),
            causal_chains=len(getattr(domain, "causal_chains", [])),
            compositions=len(getattr(domain, "compositions", [])),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "tbox_loaded": self.loaded,
            "signal_definitions": self.signal_definitions,
            "thresholds": self.thresholds,
            "policies": self.policies,
            "causal_chains": self.causal_chains,
            "compositions": self.compositions,
        }


@dataclass
class ContextFrame:
    """The agent's typed perception of its world.

    Contains entities, policies, causal chains, and graph neighborhood
    the agent needs to reason without making tool calls.

    ``world`` holds structured TBox shape data.
    The TBox itself lives in the agent's priming (system prompt).
    """

    world: WorldState = field(default_factory=WorldState)

    entities: list[ResolvedEntity] = field(default_factory=list)
    policies: list[Policy] = field(default_factory=list)
    causal_chains: list[CausalChain] = field(default_factory=list)
    neighborhood: dict[str, list[KnowledgeLink]] = field(default_factory=dict)

    document_context: str = ""
    question: str | None = None
