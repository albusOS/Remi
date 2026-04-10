"""TaskSpec — the structured work order an agent emits when delegating.

A TaskSpec is to agent delegation what a syscall is to process creation:
a typed request with constraints, lineage, and expectations. The parent
agent declares *what* it wants, the supervisor handles *how* and *when*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class HumanQuestionOption:
    """One option in a multiple-choice question posed to a human."""

    id: str
    label: str


@dataclass(frozen=True, slots=True)
class HumanQuestion:
    """A structured question that an agent tool poses to a human.

    Used by the ``ask_human`` tool to suspend a task until the user
    provides answers. The frontend renders these inline in the upload
    flow or chat UI.
    """

    id: str
    prompt: str
    kind: str = "select"  # select | text | confirm
    options: list[HumanQuestionOption] = field(default_factory=list)
    default: str | None = None
    required: bool = True


@dataclass(frozen=True, slots=True)
class TaskConstraints:
    """Resource budget and permission boundaries for a delegated task.

    The supervisor enforces these — the child agent never sees them
    directly, but the supervisor will cancel the child if it exceeds
    the budget.
    """

    max_tool_rounds: int | None = None
    max_tokens: int | None = None
    timeout_seconds: float | None = None
    allowed_tools: list[str] | None = None


@dataclass(frozen=True, slots=True)
class TaskSpec:
    """A typed work order submitted to the task supervisor.

    Fields
    ------
    agent_name:
        Which agent to run (must be registered in the workforce).
    objective:
        Natural language description of the task for the agent's prompt.
    input_data:
        Typed payload the specialist needs. Replaces the ad-hoc
        ``context`` string in the old delegation tool.
    constraints:
        Resource budget and permission boundaries.
    parent_run_id:
        The run_id of the parent agent that spawned this task.
        Used for trace correlation and cost rollup.
    metadata:
        Arbitrary key-value pairs for observability (e.g. domain
        entity ids, focus areas, originating tool name).
    """

    agent_name: str
    objective: str
    input_data: dict[str, Any] = field(default_factory=dict)
    constraints: TaskConstraints = field(default_factory=TaskConstraints)
    parent_run_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
