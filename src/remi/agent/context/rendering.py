"""LLM context rendering — formats domain knowledge into token-budgeted string blocks.

Renders assembled domain knowledge (signals, graph frames, rulebook)
into compact system message blocks for the LLM system prompt.
"""

from __future__ import annotations

import re
from typing import Any

import structlog

from remi.agent.context.frame import ContextFrame
from remi.signals import CausalChain, DomainRulebook, MutableRulebook, Policy, Signal
from remi.types.text import estimate_tokens
from remi.vectors.types import Embedder

_log = structlog.get_logger(__name__)


def render_domain_context(domain: Any) -> str:
    """Render the TBox into a compact system message block."""
    from remi.signals import DomainRulebook

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
    against the question and includes only the most relevant ones.
    Falls back to the full render when embeddings aren't available.
    """
    if question is None or embedder is None:
        return render_domain_context(domain)

    if isinstance(domain, MutableRulebook):
        pass
    elif not isinstance(domain, DomainRulebook):
        return ""

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

    try:
        texts_to_embed = [question] + [text for _, _, text in items]
        vectors = await embedder.embed(texts_to_embed)
        question_vec = vectors[0]

        scored: list[tuple[float, str, str]] = []
        for i, (section, label, _) in enumerate(items):
            item_vec = vectors[i + 1]
            dot = sum(
                a * b for a, b in zip(question_vec, item_vec, strict=True)
            )
            norm_q = sum(a * a for a in question_vec) ** 0.5
            norm_s = sum(a * a for a in item_vec) ** 0.5
            sim = dot / (norm_q * norm_s) if norm_q and norm_s else 0.0
            scored.append((sim, section, label))

        scored.sort(key=lambda x: x[0], reverse=True)

        section_counts: dict[str, int] = {}
        selected: list[tuple[str, str]] = []
        for _sim, section, label in scored:
            count = section_counts.get(section, 0)
            if count < max_items_per_section:
                selected.append((section, label))
                section_counts[section] = count + 1

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
    """Rank signals by semantic relevance to the question."""
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    def _signal_text(s: Signal) -> str:
        return f"{s.signal_type} {s.entity_name} {s.description}"

    similarity_scores: dict[str, float] = {}
    if question and embedder is not None:
        try:
            signal_texts = [_signal_text(s) for s in signals]
            all_texts = [question] + signal_texts
            all_vectors = await embedder.embed(all_texts)

            question_vec = all_vectors[0]
            for i, s in enumerate(signals):
                signal_vec = all_vectors[i + 1]
                dot = sum(
                    a * b for a, b in zip(question_vec, signal_vec, strict=True)
                )
                norm_q = sum(a * a for a in question_vec) ** 0.5
                norm_s = sum(a * a for a in signal_vec) ** 0.5
                denom = norm_q * norm_s
                similarity_scores[s.signal_id] = (
                    dot / denom if denom else 0.0
                )
        except Exception:
            _log.debug("embedding_signal_rank_failed", exc_info=True)

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
