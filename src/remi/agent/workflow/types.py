"""Workflow types — step configs, results, and DAG representation.

Everything the workflow engine operates on. Steps are the nodes,
dependencies are the edges, results accumulate as execution proceeds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from remi.agent.llm.types import TokenUsage

# ---------------------------------------------------------------------------
# Step kinds
# ---------------------------------------------------------------------------


class StepKind(StrEnum):
    """Discriminator for what a step does."""

    LLM = "llm"
    LLM_TOOLS = "llm_tools"
    TRANSFORM = "transform"
    GATE = "gate"


# ---------------------------------------------------------------------------
# Step configuration — parsed from YAML
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StepConfig:
    """A single step in a workflow DAG, parsed from YAML."""

    id: str
    kind: StepKind
    depends_on: tuple[str, ...] = ()

    # LLM / LLM_TOOLS fields
    provider: str = ""
    model: str = ""
    temperature: float = 0.0
    max_tokens: int = 4096
    response_format: str = "text"
    system_prompt: str = ""
    input_template: str = "{input}"

    # LLM_TOOLS fields
    tools: tuple[str, ...] = ()
    max_tool_rounds: int = 3

    # TRANSFORM fields
    transform: str = ""

    # GATE fields
    condition: str = ""


# ---------------------------------------------------------------------------
# Workflow defaults — from YAML top-level
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WorkflowDefaults:
    """Top-level defaults from the YAML manifest."""

    provider: str = ""
    model: str = ""
    max_concurrency: int = 4


# ---------------------------------------------------------------------------
# Workflow definition — the full parsed DAG
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WorkflowDef:
    """A complete workflow definition: defaults + ordered steps."""

    name: str
    defaults: WorkflowDefaults
    steps: tuple[StepConfig, ...]

    def step_ids(self) -> frozenset[str]:
        return frozenset(s.id for s in self.steps)

    def get_step(self, step_id: str) -> StepConfig | None:
        for s in self.steps:
            if s.id == step_id:
                return s
        return None


# ---------------------------------------------------------------------------
# Step results
# ---------------------------------------------------------------------------

StepValue = str | list | dict
"""The output value of a completed step."""


@dataclass
class StepResult:
    """Output from a single step execution."""

    step_id: str
    value: StepValue
    usage: TokenUsage = field(default_factory=TokenUsage)
    skipped: bool = False
    gated: bool = False


@dataclass
class WorkflowResult:
    """Accumulated result from a completed workflow run."""

    steps: list[StepResult] = field(default_factory=list)
    total_usage: TokenUsage = field(default_factory=TokenUsage)

    def step(self, step_id: str) -> StepValue | None:
        """Return the parsed output of a named step, or None."""
        for s in self.steps:
            if s.step_id == step_id:
                return s.value
        return None

    def step_result(self, step_id: str) -> StepResult | None:
        for s in self.steps:
            if s.step_id == step_id:
                return s
        return None
