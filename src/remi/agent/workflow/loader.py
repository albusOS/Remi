"""YAML manifest loader — parses app.yaml into validated runtime types.

Supports two manifest kinds:
  - ``kind: Workflow`` — explicit ``depends_on`` per step, parallel by default
  - ``kind: Pipeline`` — steps run sequentially in YAML order

Both produce the same ``WorkflowDef`` for the engine.

Also provides ``load_manifest_runtime`` which parses the ``runtime:``
stanza from any app.yaml (Agent, Workflow, or Pipeline) into a
``RuntimeConfig``.  This is the single parsing entry point — both the
agent runtime and workflow engine use it.

Node parsing uses Pydantic's ``TypeAdapter`` with the ``WorkflowNode``
discriminated union — YAML dicts are validated directly into typed
node models (``LLMNode``, ``TransformNode``, ``ForEachNode``, etc.).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import TypeAdapter, ValidationError

from remi.agent.runtime.config import RuntimeConfig
from remi.agent.workflow.registry import get_manifest_path
from remi.agent.workflow.types import (
    Wire,
    WorkflowDef,
    WorkflowDefaults,
    WorkflowNode,
)

_node_adapter: TypeAdapter[WorkflowNode] = TypeAdapter(WorkflowNode)


# ---------------------------------------------------------------------------
# Runtime config parsing (shared by agent + workflow loading paths)
# ---------------------------------------------------------------------------


def load_manifest_runtime(
    name: str,
    *,
    manifest_path: Path | None = None,
) -> RuntimeConfig:
    """Parse the ``runtime:`` stanza from a registered manifest.

    Returns ``RuntimeConfig()`` (all defaults) when the stanza is absent,
    so callers always get a valid object without null checks.
    """
    path = manifest_path or get_manifest_path(name)
    if not path.exists():
        return RuntimeConfig()

    with open(path) as f:
        data = yaml.safe_load(f)

    return _parse_runtime(data)


def _parse_runtime(data: dict[str, Any]) -> RuntimeConfig:
    """Extract and validate the runtime: block from raw YAML."""
    raw_runtime = data.get("runtime")
    if not raw_runtime or not isinstance(raw_runtime, dict):
        return RuntimeConfig()
    return RuntimeConfig.model_validate(raw_runtime)


# ---------------------------------------------------------------------------
# Workflow loading
# ---------------------------------------------------------------------------


def load_workflow(name: str, *, manifest_path: Path | None = None) -> WorkflowDef:
    """Load a workflow definition by registered manifest name.

    The manifest must have been registered via ``register_manifest``
    at startup.  Pass *manifest_path* to override (useful in tests).
    """
    path = manifest_path or get_manifest_path(name)
    if not path.exists():
        raise ValueError(f"No workflow config at {path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    kind = data.get("kind", "Pipeline")
    raw_steps: list[object] = data.get("steps") or []
    if not raw_steps:
        raise ValueError(f"Workflow '{name}' has no steps in {path}")

    raw_defaults = data.get("defaults") or {}
    defaults = WorkflowDefaults(
        provider=str(raw_defaults.get("provider", "")),
        model=str(raw_defaults.get("model", "")),
        max_concurrency=int(raw_defaults.get("max_concurrency", 4)),
    )

    if kind == "Workflow":
        steps = _parse_workflow_steps(raw_steps, name)
    else:
        steps = _parse_pipeline_steps(raw_steps, name)

    wires = _parse_wires(data.get("wires") or [])
    runtime = _parse_runtime(data)

    return WorkflowDef(
        name=name,
        defaults=defaults,
        steps=tuple(steps),
        wires=tuple(wires),
        runtime=runtime,
    )


def _parse_workflow_steps(raw_steps: list[object], name: str) -> list[WorkflowNode]:
    """Parse steps with explicit depends_on (kind: Workflow)."""
    steps: list[WorkflowNode] = []
    for raw in raw_steps:
        if not isinstance(raw, dict):
            raise TypeError(
                f"Step must be a mapping in workflow '{name}', got {type(raw).__name__}"
            )
        steps.append(_parse_node(raw, name))
    return steps


def _parse_pipeline_steps(raw_steps: list[object], name: str) -> list[WorkflowNode]:
    """Parse sequential steps (kind: Pipeline) — each depends on the previous."""
    steps: list[WorkflowNode] = []
    prev_id: str | None = None
    for raw in raw_steps:
        if not isinstance(raw, dict):
            raise TypeError(
                f"Step must be a mapping in pipeline '{name}', got {type(raw).__name__}"
            )
        node = _parse_node(raw, name, implicit_dep=prev_id)
        steps.append(node)
        prev_id = node.id
    return steps


def _parse_node(
    raw: dict[str, Any],
    workflow_name: str,
    implicit_dep: str | None = None,
) -> WorkflowNode:
    """Parse a single node from raw YAML dict via Pydantic TypeAdapter."""
    if "id" not in raw:
        raise ValueError(f"Every step must have an 'id' in workflow '{workflow_name}'")

    prepared = _prepare_raw(raw, implicit_dep)

    try:
        return _node_adapter.validate_python(prepared)
    except ValidationError as exc:
        raise ValueError(
            f"Invalid step '{raw.get('id', '?')}' in workflow '{workflow_name}': {exc}"
        ) from None


def _prepare_raw(
    raw: dict[str, Any],
    implicit_dep: str | None,
) -> dict[str, Any]:
    """Normalize raw YAML dict before Pydantic validation.

    Handles: implicit pipeline deps, tools as comma string, retry shorthand.
    """
    out = dict(raw)

    if "depends_on" not in out and implicit_dep is not None:
        out["depends_on"] = (implicit_dep,)
    elif "depends_on" in out:
        deps = out["depends_on"]
        if isinstance(deps, str):
            out["depends_on"] = (deps,)
        elif isinstance(deps, list):
            out["depends_on"] = tuple(deps)

    if "tools" in out and isinstance(out["tools"], str):
        out["tools"] = tuple(t.strip() for t in out["tools"].split(","))
    elif "tools" in out and isinstance(out["tools"], list):
        out["tools"] = tuple(out["tools"])

    if "retry" in out and isinstance(out["retry"], dict):
        pass  # Pydantic handles RetryPolicy validation
    elif "retry" in out and out["retry"] is True:
        out["retry"] = {"max_attempts": 3}

    return out


def _parse_wires(raw_wires: list[object]) -> list[Wire]:
    """Parse wire declarations from YAML.

    Each wire is ``{source: "step.port", target: "step.port"}``.
    """
    wires: list[Wire] = []
    for raw in raw_wires:
        if not isinstance(raw, dict):
            continue
        source = str(raw.get("source", ""))
        target = str(raw.get("target", ""))
        if "." not in source or "." not in target:
            raise ValueError(
                f"Wire endpoints must be 'step.port', got "
                f"source={source!r} target={target!r}"
            )
        src_step, src_port = source.split(".", 1)
        tgt_step, tgt_port = target.split(".", 1)
        wires.append(Wire(
            source_step=src_step,
            source_port=src_port,
            target_step=tgt_step,
            target_port=tgt_port,
            optional=bool(raw.get("optional", False)),
        ))
    return wires
