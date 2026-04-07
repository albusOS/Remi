"""YAML manifest loader — parses app.yaml into a validated WorkflowDef.

Supports two manifest kinds:
  - ``kind: Workflow`` — explicit ``depends_on`` per step, parallel by default
  - ``kind: Pipeline`` — backward compat, steps run sequentially in YAML order

Both produce the same ``WorkflowDef`` for the engine.
"""

from __future__ import annotations

import yaml

from remi.agent.workflow.types import StepConfig, StepKind, WorkflowDef, WorkflowDefaults
from remi.types.paths import AGENTS_DIR


def load_workflow(name: str) -> WorkflowDef:
    """Load a workflow definition from ``application/agents/<name>/app.yaml``."""
    path = AGENTS_DIR / name / "app.yaml"
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

    return WorkflowDef(name=name, defaults=defaults, steps=tuple(steps))


def _parse_workflow_steps(raw_steps: list[object], name: str) -> list[StepConfig]:
    """Parse steps with explicit depends_on (kind: Workflow)."""
    steps: list[StepConfig] = []
    for raw in raw_steps:
        if not isinstance(raw, dict):
            raise TypeError(
                f"Step must be a mapping in workflow '{name}', got {type(raw).__name__}"
            )
        steps.append(_parse_step(raw))
    return steps


def _parse_pipeline_steps(raw_steps: list[object], name: str) -> list[StepConfig]:
    """Parse sequential steps (kind: Pipeline) — each depends on the previous."""
    steps: list[StepConfig] = []
    prev_id: str | None = None
    for raw in raw_steps:
        if not isinstance(raw, dict):
            raise TypeError(
                f"Step must be a mapping in pipeline '{name}', got {type(raw).__name__}"
            )
        step = _parse_step(raw, implicit_dep=prev_id)
        steps.append(step)
        prev_id = step.id
    return steps


def _parse_step(raw: dict, implicit_dep: str | None = None) -> StepConfig:
    """Parse a single step from raw YAML dict."""
    step_id = str(raw.get("id", ""))
    if not step_id:
        raise ValueError("Every step must have an 'id'")

    kind_str = str(raw.get("kind", "llm"))
    try:
        kind = StepKind(kind_str)
    except ValueError:
        raise ValueError(f"Unknown step kind '{kind_str}' on step '{step_id}'") from None

    # Resolve depends_on: explicit from YAML, or implicit from pipeline ordering
    raw_deps = raw.get("depends_on")
    if raw_deps is not None:
        if isinstance(raw_deps, str):
            depends_on = (raw_deps,)
        elif isinstance(raw_deps, list):
            depends_on = tuple(str(d) for d in raw_deps)
        else:
            depends_on = ()
    elif implicit_dep is not None:
        depends_on = (implicit_dep,)
    else:
        depends_on = ()

    # Tools for llm_tools steps
    raw_tools = raw.get("tools") or []
    if isinstance(raw_tools, str):
        tools = tuple(t.strip() for t in raw_tools.split(","))
    else:
        tools = tuple(str(t) for t in raw_tools)

    return StepConfig(
        id=step_id,
        kind=kind,
        depends_on=depends_on,
        provider=str(raw.get("provider") or ""),
        model=str(raw.get("model") or ""),
        temperature=float(raw.get("temperature", 0.0)),
        max_tokens=int(raw.get("max_tokens", 4096)),
        response_format=str(raw.get("response_format", "text")),
        system_prompt=str(raw.get("system_prompt", "")),
        input_template=str(raw.get("input_template", "{input}")),
        tools=tools,
        max_tool_rounds=int(raw.get("max_tool_rounds", 3)),
        transform=str(raw.get("transform", "")),
        condition=str(raw.get("condition", "")),
    )
