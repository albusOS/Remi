"""ContextFrame — structured pre-assembled context for an agent run."""

from __future__ import annotations

from dataclasses import dataclass, field

from remi.agent.graph.retriever import ResolvedEntity
from remi.agent.graph.types import KnowledgeLink
from remi.agent.signals import CausalChain, Policy, Signal


@dataclass
class ContextFrame:
    """Structured pre-assembled context for an agent run.

    Contains everything the agent needs to reason — entities, signals,
    policies, causal chains, and graph neighborhood — without making
    tool calls to discover it.
    """

    entities: list[ResolvedEntity] = field(default_factory=list)
    signals: list[Signal] = field(default_factory=list)
    policies: list[Policy] = field(default_factory=list)
    causal_chains: list[CausalChain] = field(default_factory=list)
    neighborhood: dict[str, list[KnowledgeLink]] = field(default_factory=dict)
    domain_context: str = ""
    signal_summary: str = ""
    question: str | None = None
