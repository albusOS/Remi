"""Test unified agent wiring — director YAML, tool registry, container."""

from __future__ import annotations

from remi.config.container import Container
from remi.shared.paths import WORKFLOWS_DIR

EXPECTED_DIRECTOR_TOOLS = [
    "onto_signals",
    "onto_explain",
    "onto_search",
    "onto_get",
    "onto_related",
    "onto_aggregate",
    "onto_schema",
    "onto_timeline",
    "onto_codify_observation",
    "onto_codify_policy",
    "onto_codify_causal_link",
    "semantic_search",
    "document_list",
    "document_query",
    "sandbox_exec_python",
    "sandbox_exec_shell",
    "sandbox_write_file",
    "sandbox_read_file",
    "sandbox_list_files",
    "trace_list",
    "trace_show",
    "trace_spans",
]

REMOVED_TOOLS = [
    "portfolio_summary",
    "property_details",
    "unit_search",
    "maintenance_overview",
    "lease_expiring",
    "tenant_lookup",
    "kb_search",
    "kb_related",
    "kb_summary",
]


def test_no_redundant_tools_in_registry() -> None:
    """Removed property/knowledge tools should not be in the registry."""
    container = Container()
    registry = container.tool_registry

    for tool_name in REMOVED_TOOLS:
        assert not registry.has(tool_name), f"Removed tool '{tool_name}' is still registered"


def test_all_director_tools_exist_in_registry() -> None:
    """Every tool the director YAML references must be in the registry."""
    container = Container()
    registry = container.tool_registry

    for tool_name in EXPECTED_DIRECTOR_TOOLS:
        assert registry.has(tool_name), f"Tool '{tool_name}' listed in director YAML but not registered"


def test_specialist_yamls_removed() -> None:
    """The specialist workflows should no longer exist."""
    for name in ("portfolio_analyst", "property_inspector", "maintenance_triage"):
        path = WORKFLOWS_DIR / name / "app.yaml"
        assert not path.exists(), f"Specialist YAML still exists: {path}"


def test_remaining_workflows() -> None:
    """Only director, knowledge_enricher, and domain.yaml should remain."""
    expected = {"director", "knowledge_enricher"}
    actual = {d.name for d in WORKFLOWS_DIR.iterdir() if d.is_dir()}
    assert actual == expected, f"Unexpected workflows: {actual - expected}"
