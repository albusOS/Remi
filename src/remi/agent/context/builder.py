"""ContextBuilder — assembles token-budgeted context frames for agents.

The ContextBuilder bridges the knowledge infrastructure (ontology, signals,
entailment, graph) and the agent. Instead of the agent making tool calls
to discover context, the ContextBuilder pre-assembles a rich ContextFrame.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from remi.agent.context.frame import ContextFrame
from remi.agent.context.rendering import (
    render_active_signals,
    render_domain_context_semantic,
    render_graph_context,
)
from remi.agent.types import Message
from remi.graph.retriever import GraphRetriever
from remi.graph.stores import KnowledgeGraph
from remi.observe.events import Event
from remi.observe.types import SpanKind, Tracer
from remi.signals import DomainRulebook, MutableRulebook, SignalStore
from remi.types.text import estimate_tokens, truncate_to_tokens
from remi.vectors.types import Embedder, VectorStore

_log = structlog.get_logger(__name__)

_DEFAULT_TOKEN_BUDGET = 16_000


class ContextBuilder:
    """Assembles a ContextFrame from the knowledge graph and domain ontology.

    Phases:
    1. Render domain context (TBox -> system message block)
    2. Render active signals (ranked by semantic relevance to the question)
    3. Optionally resolve question-relevant entities via GraphRetriever

    Injection is token-budgeted: the total injected context will not
    exceed ``token_budget`` tokens (approximate, char-based estimate).
    """

    def __init__(
        self,
        domain: DomainRulebook | MutableRulebook,
        signal_store: SignalStore | None = None,
        graph_retriever: GraphRetriever | None = None,
        embedder: Embedder | None = None,
        token_budget: int = _DEFAULT_TOKEN_BUDGET,
    ) -> None:
        self._domain = domain
        self._signal_store = signal_store
        self._graph_retriever = graph_retriever
        self._embedder = embedder
        self._token_budget = token_budget

    async def build(
        self,
        question: str | None = None,
        *,
        tracer: Tracer | None = None,
        phases: set[str] | None = None,
    ) -> ContextFrame:
        """Build a context frame, optionally restricted to *phases*.

        *phases* controls which injection steps run. Valid values:
        ``"domain"``, ``"signals"``, ``"graph"``, ``"memory"``.
        When ``None``, all phases run (backward-compatible default).
        """
        frame = ContextFrame()
        frame.question = question
        run_all = phases is None
        needs_domain = run_all or (phases is not None and "domain" in phases)
        needs_signals = run_all or (phases is not None and "signals" in phases)
        needs_graph = run_all or (phases is not None and "graph" in phases)

        if needs_domain:
            frame.domain_context = await render_domain_context_semantic(
                self._domain, question=question, embedder=self._embedder,
            )
            frame.policies = list(getattr(self._domain, "policies", []))
            frame.causal_chains = list(getattr(self._domain, "causal_chains", []))
            if tracer is not None and frame.domain_context:
                async with tracer.span(
                    SpanKind.PERCEPTION,
                    "tbox_injection",
                    signal_definitions=len(getattr(self._domain, "signals", {})),
                    threshold_count=len(getattr(self._domain, "thresholds", {})),
                    policy_count=len(getattr(self._domain, "policies", [])),
                    causal_chain_count=len(getattr(self._domain, "causal_chains", [])),
                ):
                    pass

        async def _fetch_signals() -> None:
            if not (needs_signals and self._signal_store is not None):
                return
            frame.signal_summary = await render_active_signals(
                self._signal_store,
                question=question,
                embedder=self._embedder,
            )
            try:
                frame.signals = await self._signal_store.list_signals()
            except Exception:
                _log.warning("signal_list_fetch_failed", exc_info=True)
            if tracer is not None:
                severity_counts: dict[str, int] = {}
                for s in frame.signals:
                    sev = s.severity.value if hasattr(s.severity, "value") else str(s.severity)
                    severity_counts[sev] = severity_counts.get(sev, 0) + 1
                async with tracer.span(
                    SpanKind.PERCEPTION,
                    "signal_injection",
                    active_signals=len(frame.signals),
                    severity_breakdown=severity_counts,
                    signal_types=[s.signal_type for s in frame.signals][:25],
                ):
                    pass

        async def _fetch_graph() -> None:
            if not (needs_graph and self._graph_retriever is not None and question):
                return
            try:
                retrieval = await self._graph_retriever.retrieve(question)
                frame.entities = retrieval.entities
                frame.neighborhood = retrieval.neighborhood
                if retrieval.signals:
                    seen = {s.signal_id for s in frame.signals}
                    for s in retrieval.signals:
                        if s.signal_id not in seen:
                            frame.signals.append(s)
                if tracer is not None:
                    total_links = sum(len(links) for links in frame.neighborhood.values())
                    async with tracer.span(
                        SpanKind.GRAPH,
                        "graph_retrieval",
                        question_length=len(question),
                        entities_resolved=len(frame.entities),
                        neighborhood_links=total_links,
                        entity_types=[e.entity_type for e in frame.entities][:10],
                        signals_attached=len(retrieval.signals),
                    ):
                        pass
            except Exception:
                _log.warning(Event.GRAPH_RETRIEVAL_FAILED, exc_info=True)

        await asyncio.gather(_fetch_signals(), _fetch_graph())

        return frame

    def inject_into_thread(
        self,
        thread: list[Message],
        frame: ContextFrame,
    ) -> None:
        """Inject the context frame into the thread as system messages.

        Respects the token budget: measures what is already in the thread
        and allocates the remaining budget across domain context, signal
        summary, and graph context in priority order.
        """
        existing_tokens = sum(estimate_tokens(str(m.content)) for m in thread if m.content)
        remaining = self._token_budget - existing_tokens
        insert_idx = 1

        if frame.domain_context and remaining > 0:
            cost = estimate_tokens(frame.domain_context)
            if cost <= remaining:
                thread.insert(insert_idx, Message(role="system", content=frame.domain_context))
                remaining -= cost
                insert_idx += 1
            else:
                trimmed = truncate_to_tokens(frame.domain_context, remaining)
                if trimmed:
                    thread.insert(insert_idx, Message(role="system", content=trimmed))
                    remaining -= estimate_tokens(trimmed)
                    insert_idx += 1

        if frame.signal_summary and remaining > 200:
            signal_budget = remaining // 2
            cost = estimate_tokens(frame.signal_summary)
            if cost <= signal_budget:
                thread.insert(insert_idx, Message(role="system", content=frame.signal_summary))
                remaining -= cost
                insert_idx += 1
            else:
                trimmed = truncate_to_tokens(frame.signal_summary, signal_budget)
                if trimmed:
                    thread.insert(insert_idx, Message(role="system", content=trimmed))
                    remaining -= estimate_tokens(trimmed)
                    insert_idx += 1

        if remaining > 200:
            graph_ctx = render_graph_context(frame, max_tokens=remaining)
            if graph_ctx:
                thread.insert(insert_idx, Message(role="system", content=graph_ctx))


def build_context_builder(
    *,
    domain: DomainRulebook | MutableRulebook,
    signal_store: SignalStore,
    knowledge_graph: KnowledgeGraph,
    vector_store: VectorStore | None = None,
    embedder: Embedder | None = None,
) -> ContextBuilder:
    """Factory: assembles a ContextBuilder with its GraphRetriever."""
    graph_retriever = GraphRetriever(
        knowledge_graph=knowledge_graph,
        vector_store=vector_store,
        embedder=embedder,
        signal_store=signal_store,
    )
    return ContextBuilder(
        domain=domain,
        signal_store=signal_store,
        graph_retriever=graph_retriever,
        embedder=embedder,
    )
