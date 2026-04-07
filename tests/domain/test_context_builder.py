"""Tests for ContextBuilder graph context rendering, injection, and token budgeting."""

from __future__ import annotations

from remi.agent.context.builder import ContextBuilder
from remi.agent.context.frame import ContextFrame, WorldState
from remi.agent.context.rendering import render_domain_context, render_graph_context
from remi.agent.graph.retrieval.retriever import ResolvedEntity
from remi.agent.graph.types import KnowledgeLink
from remi.agent.signals import DomainTBox, load_domain_yaml
from remi.agent.types import Message
from remi.types.text import estimate_tokens, truncate_to_tokens

# -- token utilities ----------------------------------------------------------


def test_estimate_tokens_basic() -> None:
    assert estimate_tokens("") == 1
    assert estimate_tokens("hello world") >= 1
    assert estimate_tokens("a" * 400) == 100


def test_truncate_to_tokens_no_op() -> None:
    short = "Hello world"
    assert truncate_to_tokens(short, 100) == short


def test_truncate_to_tokens_cuts() -> None:
    long = "Line one\nLine two\nLine three\nLine four\n" * 100
    result = truncate_to_tokens(long, 50)
    assert estimate_tokens(result) <= 55  # rough, not exact
    assert len(result) < len(long)


# -- render_graph_context -----------------------------------------------------


def test_render_graph_context_empty_entities() -> None:
    frame = ContextFrame()
    assert render_graph_context(frame) == ""


def test_render_graph_context_with_entities() -> None:
    frame = ContextFrame(
        entities=[
            ResolvedEntity(
                entity_id="prop-1",
                entity_type="Property",
                properties={"name": "100 Smithfield St", "year_built": 2010},
                score=0.85,
            ),
        ],
    )

    result = render_graph_context(frame)
    assert "100 Smithfield St" in result
    assert "Property" in result
    assert "0.85" in result
    assert "Graph Context" in result


def test_render_graph_context_with_neighborhood() -> None:
    frame = ContextFrame(
        entities=[
            ResolvedEntity(
                entity_id="prop-1",
                entity_type="Property",
                properties={"name": "100 Smithfield St"},
                score=0.9,
            ),
        ],
        neighborhood={
            "prop-1": [
                KnowledgeLink(
                    source_id="prop-1",
                    link_type="MANAGED_BY",
                    target_id="mgr-1",
                ),
                KnowledgeLink(
                    source_id="unit-1",
                    link_type="BELONGS_TO",
                    target_id="prop-1",
                ),
            ],
        },
    )

    result = render_graph_context(frame)
    assert "MANAGED_BY" in result
    assert "BELONGS_TO" in result
    assert "mgr-1" in result
    assert "unit-1" in result


def test_render_graph_context_caps_entities() -> None:
    entities = [
        ResolvedEntity(
            entity_id=f"e-{i}",
            entity_type="Unit",
            properties={"name": f"Unit {i}"},
            score=0.5 + i * 0.01,
        )
        for i in range(10)
    ]
    frame = ContextFrame(entities=entities)

    result = render_graph_context(frame, max_entities=3)
    assert "3 relevant entities" in result


def test_render_graph_context_respects_max_tokens() -> None:
    """Entities that exceed max_tokens budget are dropped."""
    entities = [
        ResolvedEntity(
            entity_id=f"e-{i}",
            entity_type="Property",
            properties={"name": f"Property {i}", "description": "x" * 200},
            score=0.9 - i * 0.01,
        )
        for i in range(20)
    ]
    frame = ContextFrame(entities=entities)

    result = render_graph_context(frame, max_entities=20, max_tokens=300)
    assert estimate_tokens(result) <= 350  # some slack for the footer


# -- render_domain_context includes compositions ------------------------------


def test_render_domain_context_includes_compositions() -> None:
    domain = DomainTBox.from_yaml(load_domain_yaml())
    result = render_domain_context(domain)

    assert "Composition rules" in result or "Composition signals" in result
    assert "DelinquencyLeaseCliff" in result
    assert "OperationalBreakdown" in result
    assert "DecliningPortfolio" in result


# -- token-budgeted injection -------------------------------------------------


def test_inject_respects_token_budget() -> None:
    """When the thread already consumes most of the budget, injection is limited."""
    builder = ContextBuilder(
        domain=DomainTBox(),
        token_budget=500,
    )
    big_prompt = "x" * 1800  # ~450 tokens
    thread = [
        Message(role="system", content=big_prompt),
        Message(role="user", content="hello"),
    ]
    frame = ContextFrame(
        document_context="Document context " * 50,
    )

    builder.inject_into_thread(thread, frame)

    total_tokens = sum(estimate_tokens(str(m.content)) for m in thread)
    assert total_tokens <= 600


def test_inject_includes_document_context_when_budget_allows() -> None:
    """Document context is injected when there is budget headroom."""
    builder = ContextBuilder(
        domain=DomainTBox(),
        token_budget=50_000,
    )
    thread = [
        Message(role="system", content="You are a helpful assistant."),
        Message(role="user", content="hello"),
    ]
    frame = ContextFrame(
        document_context="Relevant knowledge base passages:\n- [doc.pdf]: excerpt here.",
    )

    builder.inject_into_thread(thread, frame)

    contents = [str(m.content) for m in thread]
    assert any("Relevant knowledge base" in c for c in contents)


# -- WorldState ---------------------------------------------------------------

def test_world_state_from_tbox() -> None:
    tbox = DomainTBox.from_yaml(load_domain_yaml())
    world = WorldState.from_tbox(tbox)
    assert world.loaded
    assert world.signal_definitions > 0
    assert world.thresholds > 0
    assert world.policies > 0
    assert world.causal_chains > 0
    d = world.to_dict()
    assert d["tbox_loaded"] is True
    assert "compositions" in d


def test_world_state_none_tbox() -> None:
    world = WorldState.from_tbox(None)
    assert not world.loaded
    assert world.signal_definitions == 0
