"""Knowledge graph seeding — register types, link types, and operational knowledge.

Separated from ``schema`` so the declaration module stays pure data
and the seeding module owns the I/O-bound async work.

Operational knowledge (causal chains, policies, workflows) is loaded via
``DomainTBox.from_yaml`` so the YAML shape is validated against typed Pydantic
models before any graph write — a malformed domain.yaml raises at seed time,
not silently at query time.

The seeder creates three layers of connectivity:

1. **Workflow sequencing** — process steps linked by FOLLOWS edges.
2. **Entity bindings** — APPLIES_TO edges from process steps to the entity
   types they involve; GOVERNS edges from policies to entity types.
3. **Causal → signal** — MANIFESTS_AS edges from causal phenomena to the
   named signals they produce, plus CAUSES edges between phenomena.

Together these let the agent traverse from a concrete entity (e.g. a Tenant)
→ the workflow steps that involve tenants → the policies that govern those
steps → the causal chains that explain what goes wrong → the signals that
detect it.
"""

from __future__ import annotations

from pathlib import Path

import structlog

from remi.agent.graph import KnowledgeGraph, KnowledgeProvenance
from remi.agent.signals import CausalChain, DomainTBox, Policy, WorkflowSeed
from remi.application.infra.graph.schema import (
    _ALL_TYPE_DEFS,
    _OPERATIONAL_LINKS,
    _STRUCTURAL_LINKS,
    load_domain_yaml,
)

logger = structlog.get_logger(__name__)


async def seed_knowledge_graph(
    store: KnowledgeGraph,
    domain_yaml_path: Path | None = None,
) -> None:
    """Register core types, link types, and seed operational knowledge."""

    raw = load_domain_yaml(domain_yaml_path)
    tbox = DomainTBox.from_yaml(raw)

    for type_def in _ALL_TYPE_DEFS:
        await store.define_object_type(type_def)

    for link_def in _STRUCTURAL_LINKS:
        await store.define_link_type(link_def)
    for link_def in _OPERATIONAL_LINKS:
        await store.define_link_type(link_def)

    await _seed_entity_type_nodes(store)

    for wf in tbox.workflows:
        await _seed_workflow(store, wf)

    for chain in tbox.causal_chains:
        await _seed_causal_chain(store, chain, tbox)

    for policy in tbox.policies:
        await _seed_policy(store, policy)

    for sig_def in tbox.signals.values():
        await _seed_signal_node(store, sig_def.name, sig_def.description, sig_def.entity)

    logger.info(
        "knowledge_graph_seeded",
        types=len(_ALL_TYPE_DEFS),
        workflows=len(tbox.workflows),
        policies=len(tbox.policies),
        causal_chains=len(tbox.causal_chains),
        signals=len(tbox.signals),
    )


# ---------------------------------------------------------------------------
# Entity type anchor nodes
# ---------------------------------------------------------------------------

_ENTITY_TYPE_IDS = [
    "Lease",
    "Tenant",
    "Unit",
    "Property",
    "PropertyManager",
    "Owner",
    "Vendor",
    "MaintenanceRequest",
]


async def _seed_entity_type_nodes(store: KnowledgeGraph) -> None:
    """Create anchor nodes for each entity type so policies and processes can link to them."""
    for name in _ENTITY_TYPE_IDS:
        await store.put_object(
            "entity_type",
            f"type:{name}",
            {
                "name": name,
                "provenance": KnowledgeProvenance.SEEDED.value,
            },
        )


# ---------------------------------------------------------------------------
# Workflows
# ---------------------------------------------------------------------------


async def _seed_workflow(store: KnowledgeGraph, wf: WorkflowSeed) -> None:
    for step in wf.steps:
        await store.put_object(
            "process",
            step.id,
            {
                "name": step.id.split(":")[-1],
                "description": step.description,
                "workflow": wf.name,
                "provenance": KnowledgeProvenance.SEEDED.value,
            },
        )
        for entity_type in step.applies_to:
            await store.put_link(step.id, "APPLIES_TO", f"type:{entity_type}")

    for i in range(len(wf.steps) - 1):
        await store.put_link(wf.steps[i].id, "FOLLOWS", wf.steps[i + 1].id)


# ---------------------------------------------------------------------------
# Causal chains
# ---------------------------------------------------------------------------


async def _seed_causal_chain(store: KnowledgeGraph, chain: CausalChain, tbox: DomainTBox) -> None:
    source_id = f"cause:{chain.cause}"
    target_id = f"cause:{chain.effect}"

    await store.put_object(
        "cause",
        source_id,
        {
            "name": chain.cause,
            "description": chain.description,
            "provenance": KnowledgeProvenance.SEEDED.value,
        },
    )
    await store.put_object(
        "cause",
        target_id,
        {
            "name": chain.effect,
            "provenance": KnowledgeProvenance.SEEDED.value,
        },
    )
    await store.put_link(
        source_id, "CAUSES", target_id, properties={"description": chain.description}
    )

    if chain.manifests_as and chain.manifests_as in tbox.signals:
        await store.put_link(source_id, "MANIFESTS_AS", f"signal:{chain.manifests_as}")


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------


async def _seed_signal_node(
    store: KnowledgeGraph,
    name: str,
    description: str,
    entity: str,
) -> None:
    """Create a signal node and link it to the entity type it measures."""
    await store.put_object(
        "signal",
        f"signal:{name}",
        {
            "name": name,
            "description": description,
            "entity": entity,
            "provenance": KnowledgeProvenance.SEEDED.value,
        },
    )
    await store.put_link(f"signal:{name}", "MEASURED_BY", f"type:{entity}")


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------


async def _seed_policy(store: KnowledgeGraph, policy: Policy) -> None:
    await store.put_object(
        "policy",
        policy.id,
        {
            "description": policy.description,
            "trigger": policy.trigger,
            "deontic": policy.deontic.value,
            "provenance": KnowledgeProvenance.SEEDED.value,
        },
    )
    for entity_type in policy.governs:
        await store.put_link(policy.id, "GOVERNS", f"type:{entity_type}")
