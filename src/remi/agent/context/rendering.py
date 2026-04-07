"""LLM context rendering — projects typed perception into prose for injection.

``render_domain_context`` renders TBox knowledge for agent priming (once).
``render_graph_context`` renders entity neighborhood for per-turn injection.
"""

from __future__ import annotations

import re
from typing import Any

from remi.agent.context.frame import ContextFrame
from remi.agent.signals import DomainTBox, MutableTBox
from remi.types.text import estimate_tokens


def render_domain_context(domain: Any, *, compact: bool = False) -> str:
    """Render the TBox into a system message block for agent priming.

    When *compact* is True, only signal names/severities and composition
    rules are emitted — thresholds, policies, and causal chains are
    omitted.  Use compact mode for agents that query signals via tools
    rather than reasoning over the full ontology (e.g. researcher).
    """
    if isinstance(domain, MutableTBox):
        pass
    elif not isinstance(domain, DomainTBox):
        return ""

    shape_parts: list[str] = []
    sig_count = len(getattr(domain, "signals", {}))
    thr_count = len(getattr(domain, "thresholds", {}))
    pol_count = len(getattr(domain, "policies", []))
    cc_count = len(getattr(domain, "causal_chains", []))
    if sig_count:
        shape_parts.append(f"{sig_count} signals")
    if not compact:
        if thr_count:
            shape_parts.append(f"{thr_count} thresholds")
        if pol_count:
            shape_parts.append(f"{pol_count} policies")
        if cc_count:
            shape_parts.append(f"{cc_count} causal chains")
    shape_label = f"TBox: {', '.join(shape_parts)}" if shape_parts else "from TBox"
    parts = [f"## Domain Context ({shape_label})\n"]

    signals = getattr(domain, "signals", {})
    if signals:
        signal_lines = []
        for defn in signals.values() if isinstance(signals, dict) else signals:
            if compact:
                signal_lines.append(f"- {defn.name} [{defn.severity.value}] ({defn.entity})")
            else:
                desc = defn.description.split("\n")[0].strip()
                signal_lines.append(
                    f"- **{defn.name}** [{defn.severity.value}] ({defn.entity}): {desc}"
                )
        parts.append("**Signal definitions (what the agent detects):**")
        parts.append("\n".join(signal_lines))

    if not compact:
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
                direction = "\u2192" if link.source_id == entity.entity_id else "\u2190"
                other_id = link.target_id if link.source_id == entity.entity_id else link.source_id
                entity_lines.append(f"  - {direction} {link.link_type} \u2192 `{other_id}`")

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
    """Find TBox signal definition names mentioned in the agent's output."""
    if domain is None or not hasattr(domain, "all_signal_names"):
        return []
    found = []
    for name in domain.all_signal_names():
        if re.search(rf"\b{re.escape(name)}\b", text, re.IGNORECASE):
            found.append(name)
    return found
