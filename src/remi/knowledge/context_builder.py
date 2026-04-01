"""GraphRAG context assembly — builds structured context frames for agents.

The ContextBuilder is the bridge between the knowledge infrastructure
(ontology, signals, entailment, graph) and the agent. Instead of the
agent making tool calls to discover context, the ContextBuilder
pre-assembles a rich, typed ContextFrame.

Token-budgeted: each injection phase checks remaining budget and
truncates or drops sections that would exceed it.
"""

from __future__ import annotations

import asyncio
import contextlib
import re
from dataclasses import dataclass, field
from typing import Any

import structlog

from remi.knowledge.graph_retriever import GraphRetriever, ResolvedEntity
from remi.models.chat import Message
from remi.models.ontology import KnowledgeGraph, KnowledgeLink
from remi.models.signals import (
    CausalChain,
    DomainRulebook,
    MutableRulebook,
    Policy,
    Signal,
    SignalStore,
)
from remi.models.trace import SpanKind
from remi.observability.events import Event
from remi.observability.tracer import Tracer
from remi.vectors.ports import Embedder, VectorStore
from remi.vectors.tokens import estimate_tokens, truncate_to_tokens

_log = structlog.get_logger(__name__)

_DEFAULT_TOKEN_BUDGET = 16_000


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


class ContextBuilder:
    """Assembles a ContextFrame from the knowledge graph and domain ontology.

    Phases:
    1. Render domain context (TBox -> system message block)
    2. Render active signals (ranked by semantic relevance to the question)
    3. Optionally resolve question-relevant entities via GraphRetriever

    Injection is token-budgeted: the total injected context will not
    exceed ``token_budget`` tokens (approximate, char-based estimate).

    When an embedder is available, signal ranking and domain context
    selection use embedding similarity rather than keyword overlap.
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
        needs_domain = run_all or "domain" in phases
        needs_signals = run_all or "signals" in phases
        needs_graph = run_all or "graph" in phases

        # Domain context — semantic retrieval when embedder is available
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

        # Signal fetch and graph retrieval are independent I/O — run concurrently
        async def _fetch_signals() -> None:
            if not (needs_signals and self._signal_store is not None):
                return
            frame.signal_summary = await render_active_signals(
                self._signal_store,
                question=question,
                embedder=self._embedder,
            )
            with contextlib.suppress(Exception):
                frame.signals = await self._signal_store.list_signals()
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

        # Priority 1: Domain context (TBox) — always if it fits
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

        # Priority 2: Signal summary — up to half of remaining budget
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

        # Priority 3: Graph context — whatever budget is left
        if remaining > 200:
            graph_ctx = render_graph_context(frame, max_tokens=remaining)
            if graph_ctx:
                thread.insert(insert_idx, Message(role="system", content=graph_ctx))


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


def render_domain_context(domain: Any) -> str:
    """Render the TBox into a compact system message block."""
    from remi.models.signals import DomainRulebook

    if isinstance(domain, MutableRulebook):
        pass
    elif not isinstance(domain, DomainRulebook):
        return ""

    parts = ["## Domain Context (from rulebook)\n"]

    signals = getattr(domain, "signals", {})
    if signals:
        signal_lines = []
        for defn in signals.values() if isinstance(signals, dict) else signals:
            desc = defn.description.split("\n")[0].strip()
            signal_lines.append(
                f"- **{defn.name}** [{defn.severity.value}] ({defn.entity}): {desc}"
            )
        parts.append("**Signal definitions (what the entailment engine detects):**")
        parts.append("\n".join(signal_lines))

    thresholds = getattr(domain, "thresholds", {})
    if thresholds:
        threshold_lines = [f"- {key}: {val}" for key, val in thresholds.items()]
        parts.append("\n**Operational thresholds:**")
        parts.append("\n".join(threshold_lines))

    policies = getattr(domain, "policies", [])
    if policies:
        policy_lines = [f"- [{pol.deontic.value}] {pol.description}" for pol in policies]
        parts.append("\n**Deontic obligations:**")
        parts.append("\n".join(policy_lines))

    causal_chains = getattr(domain, "causal_chains", [])
    if causal_chains:
        chain_lines = [f"- {c.cause} → {c.effect}: {c.description}" for c in causal_chains]
        parts.append("\n**Known causal relationships:**")
        parts.append("\n".join(chain_lines))

    compositions = getattr(domain, "compositions", [])
    if compositions:
        comp_lines = []
        for comp in compositions:
            sev = comp.severity.value if hasattr(comp.severity, "value") else str(comp.severity)
            constituents = " + ".join(comp.constituents)
            comp_lines.append(
                f"- **{comp.name}** [{sev}] = {constituents}: "
                f"{comp.description.split(chr(10))[0].strip()}"
            )
        parts.append("\n**Composition rules (compound signals from co-occurring signals):**")
        parts.append("\n".join(comp_lines))

    parts.append("\nComposition signals indicate compounding situations — prioritize them.")
    return "\n".join(parts)


async def render_domain_context_semantic(
    domain: Any,
    *,
    question: str | None = None,
    embedder: Embedder | None = None,
    max_items_per_section: int = 8,
) -> str:
    """Render domain context, semantically filtered when possible.

    When an embedder and question are available, scores each domain rule
    (signal definition, threshold, policy, causal chain) against the
    question and includes only the most relevant ones. Falls back to
    the full render when embeddings aren't available.
    """
    if question is None or embedder is None:
        return render_domain_context(domain)

    if isinstance(domain, MutableRulebook):
        pass
    elif not isinstance(domain, DomainRulebook):
        return ""

    # Collect all domain items as (section, label, text) triples
    items: list[tuple[str, str, str]] = []

    signals = getattr(domain, "signals", {})
    for defn in signals.values() if isinstance(signals, dict) else signals:
        desc = defn.description.split("\n")[0].strip()
        text = f"{defn.name} {defn.severity.value} {defn.entity}: {desc}"
        label = f"- **{defn.name}** [{defn.severity.value}] ({defn.entity}): {desc}"
        items.append(("signals", label, text))

    thresholds = getattr(domain, "thresholds", {})
    for key, val in thresholds.items():
        text = f"{key}: {val}"
        label = f"- {key}: {val}"
        items.append(("thresholds", label, text))

    policies = getattr(domain, "policies", [])
    for pol in policies:
        text = f"{pol.deontic.value} {pol.description}"
        label = f"- [{pol.deontic.value}] {pol.description}"
        items.append(("policies", label, text))

    causal_chains = getattr(domain, "causal_chains", [])
    for c in causal_chains:
        text = f"{c.cause} causes {c.effect}: {c.description}"
        label = f"- {c.cause} → {c.effect}: {c.description}"
        items.append(("causal", label, text))

    compositions = getattr(domain, "compositions", [])
    for comp in compositions:
        sev = comp.severity.value if hasattr(comp.severity, "value") else str(comp.severity)
        constituents = " + ".join(comp.constituents)
        text = f"{comp.name} {sev} {constituents}: {comp.description.split(chr(10))[0].strip()}"
        label = (
            f"- **{comp.name}** [{sev}] = {constituents}: "
            f"{comp.description.split(chr(10))[0].strip()}"
        )
        items.append(("compositions", label, text))

    if not items:
        return ""

    # Embed question + all items in one batch
    try:
        texts_to_embed = [question] + [text for _, _, text in items]
        vectors = await embedder.embed(texts_to_embed)
        question_vec = vectors[0]

        scored: list[tuple[float, str, str]] = []
        for i, (section, label, _) in enumerate(items):
            item_vec = vectors[i + 1]
            dot = sum(a * b for a, b in zip(question_vec, item_vec))
            norm_q = sum(a * a for a in question_vec) ** 0.5
            norm_s = sum(a * a for a in item_vec) ** 0.5
            sim = dot / (norm_q * norm_s) if norm_q and norm_s else 0.0
            scored.append((sim, section, label))

        scored.sort(key=lambda x: x[0], reverse=True)

        # Group by section, keeping order, cap per section
        section_counts: dict[str, int] = {}
        selected: list[tuple[str, str]] = []
        for sim, section, label in scored:
            count = section_counts.get(section, 0)
            if count < max_items_per_section:
                selected.append((section, label))
                section_counts[section] = count + 1

        # Render grouped by section
        section_headers = {
            "signals": "**Signal definitions (what the entailment engine detects):**",
            "thresholds": "**Operational thresholds:**",
            "policies": "**Deontic obligations:**",
            "causal": "**Known causal relationships:**",
            "compositions": "**Composition rules (compound signals from co-occurring signals):**",
        }
        parts = ["## Domain Context (semantically matched to your question)\n"]
        current_section = ""
        for section, label in selected:
            if section != current_section:
                if current_section:
                    parts.append("")
                parts.append(section_headers.get(section, f"**{section}:**"))
                current_section = section
            parts.append(label)

        if len(parts) > 1:
            parts.append("\nComposition signals indicate compounding situations — prioritize them.")
            return "\n".join(parts)

    except Exception:
        _log.debug("semantic_domain_context_failed", exc_info=True)

    # Fall back to full render
    return render_domain_context(domain)


async def render_active_signals(
    signal_store: Any,
    *,
    question: str | None = None,
    embedder: Embedder | None = None,
    max_signals: int = 15,
) -> str:
    """Fetch current signals, rank by semantic relevance, and render a compact summary."""
    try:
        signals = await signal_store.list_signals()
    except Exception:
        _log.warning("signal_summary_fetch_failed", exc_info=True)
        return ""

    if not signals:
        return (
            "## Active Signals (0)\n\n"
            "No signals currently active. The portfolio appears within normal parameters. "
            "If the user asks about problems, verify by querying the data directly."
        )

    ranked = await _rank_signals(signals, question, embedder)
    ranked = ranked[:max_signals]

    severity_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}

    lines = [f"## Active Signals ({len(signals)} total, showing top {len(ranked)})\n"]
    for s in ranked:
        sev_val = s.severity.value if hasattr(s.severity, "value") else str(s.severity)
        icon = severity_icon.get(sev_val, "❓")
        desc = s.description[:120] + ("…" if len(s.description) > 120 else "")
        lines.append(
            f"- {icon} **[{sev_val.upper()}] {s.signal_type}**: "
            f"{s.entity_name} — {desc}  \n"
            f"  `{s.signal_id}`"
        )

    lines.append(
        "\nThese signals are pre-computed from the data. Reference them by name in your response."
    )
    return "\n".join(lines)


async def _rank_signals(
    signals: list[Signal],
    question: str | None,
    embedder: Embedder | None = None,
) -> list[Signal]:
    """Rank signals by semantic relevance to the question.

    When an embedder is available, computes cosine similarity between
    the question embedding and each signal's text representation. Falls
    back to keyword overlap when no embedder is configured.
    """
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    def _signal_text(s: Signal) -> str:
        return f"{s.signal_type} {s.entity_name} {s.description}"

    # Try embedding-based ranking first
    similarity_scores: dict[str, float] = {}
    if question and embedder is not None:
        try:
            signal_texts = [_signal_text(s) for s in signals]
            all_texts = [question] + signal_texts
            all_vectors = await embedder.embed(all_texts)

            question_vec = all_vectors[0]
            for i, s in enumerate(signals):
                signal_vec = all_vectors[i + 1]
                dot = sum(a * b for a, b in zip(question_vec, signal_vec))
                norm_q = sum(a * a for a in question_vec) ** 0.5
                norm_s = sum(a * a for a in signal_vec) ** 0.5
                similarity_scores[s.signal_id] = dot / (norm_q * norm_s) if norm_q and norm_s else 0.0
        except Exception:
            _log.debug("embedding_signal_rank_failed", exc_info=True)

    # Keyword overlap fallback when embeddings aren't available
    keyword_scores: dict[str, int] = {}
    if not similarity_scores and question:
        question_words = {w.lower() for w in re.findall(r"[a-zA-Z]{3,}", question)}
        for s in signals:
            haystack_words = set(re.findall(r"[a-zA-Z]{3,}", _signal_text(s).lower()))
            keyword_scores[s.signal_id] = len(question_words & haystack_words)

    def sort_key(s: Signal) -> tuple[int, int, float, str]:
        sev = s.severity.value if hasattr(s.severity, "value") else str(s.severity)
        tier = severity_order.get(sev, 4)
        is_composite = "composition_rule" in (s.evidence or {})
        composite_boost = 0 if is_composite else 1

        if similarity_scores:
            relevance = -similarity_scores.get(s.signal_id, 0.0)
        else:
            relevance = -float(keyword_scores.get(s.signal_id, 0))

        return (composite_boost, tier, relevance, s.signal_type)

    return sorted(signals, key=sort_key)


def render_graph_context(
    frame: ContextFrame,
    *,
    max_entities: int = 5,
    max_links_per_entity: int = 10,
    max_tokens: int = 4000,
) -> str:
    """Render resolved entities and their graph neighborhood for the LLM."""
    if not frame.entities:
        return ""

    entities = sorted(frame.entities, key=lambda e: e.score, reverse=True)[:max_entities]
    entity_ids = {e.entity_id for e in entities}
    entity_signals: dict[str, list[Signal]] = {}
    for s in frame.signals:
        if s.entity_id in entity_ids:
            entity_signals.setdefault(s.entity_id, []).append(s)

    lines = [f"## Graph Context ({len(entities)} relevant entities)\n"]
    token_count = estimate_tokens("\n".join(lines))

    for entity in entities:
        entity_lines: list[str] = []
        name = entity.properties.get("name", entity.entity_id)
        entity_lines.append(
            f"### {entity.entity_type}: {name}"
            f"  (id=`{entity.entity_id}`, relevance={entity.score:.2f})"
        )

        display_props = {
            k: v for k, v in entity.properties.items() if k not in ("text",) and v is not None
        }
        if display_props:
            prop_parts = [f"{k}={v}" for k, v in list(display_props.items())[:8]]
            entity_lines.append(f"  Properties: {', '.join(prop_parts)}")

        links = frame.neighborhood.get(entity.entity_id, [])[:max_links_per_entity]
        if links:
            entity_lines.append("  Relationships:")
            for link in links:
                direction = "→" if link.source_id == entity.entity_id else "←"
                other_id = link.target_id if link.source_id == entity.entity_id else link.source_id
                entity_lines.append(f"  - {direction} {link.link_type} → `{other_id}`")

        sigs = entity_signals.get(entity.entity_id, [])
        for sig in sigs:
            sev = sig.severity.value if hasattr(sig.severity, "value") else str(sig.severity)
            entity_lines.append(
                f"  Active signal: [{sev.upper()}] {sig.signal_type} — {sig.description[:100]}"
            )

        entity_lines.append("")

        chunk_cost = estimate_tokens("\n".join(entity_lines))
        if token_count + chunk_cost > max_tokens:
            break
        lines.extend(entity_lines)
        token_count += chunk_cost

    if len(lines) <= 1:
        return ""

    lines.append(
        "This graph context was pre-fetched based on your question. Use it to ground your answer."
    )
    return "\n".join(lines)


def extract_signal_references(text: str, domain: Any) -> list[str]:
    """Find signal names mentioned in the agent's output."""
    if domain is None or not hasattr(domain, "all_signal_names"):
        return []
    found = []
    for name in domain.all_signal_names():
        if re.search(rf"\b{re.escape(name)}\b", text, re.IGNORECASE):
            found.append(name)
    return found


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
