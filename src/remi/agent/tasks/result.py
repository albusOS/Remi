"""TaskResult — structured output from a completed task.

Replaces the raw ``(str | None, str)`` tuple that delegation returned.
The parent agent gets typed output it can reason over programmatically,
plus metadata for cost tracking and trace correlation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class TaskUsage:
    """Token and cost accounting for a completed task."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    tool_calls: int = 0
    estimated_cost: float | None = None


@dataclass(frozen=True, slots=True)
class TaskResult:
    """Structured output from a delegated task.

    Fields
    ------
    ok:
        Whether the task completed successfully.
    output:
        The specialist's primary output (typically the answer text).
    data:
        Structured data the specialist produced (parsed JSON, etc.).
        ``None`` if the specialist only produced prose.
    error:
        Human-readable error message on failure.
    run_id:
        The run_id assigned to this task execution.
    usage:
        Token/cost accounting for the full task run.
    metadata:
        Provenance, timing, or debug information.
    """

    ok: bool = True
    output: str | None = None
    data: dict[str, Any] | None = None
    error: str | None = None
    run_id: str = ""
    usage: TaskUsage = field(default_factory=TaskUsage)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success(
        cls,
        output: str | None,
        *,
        run_id: str = "",
        data: dict[str, Any] | None = None,
        usage: TaskUsage | None = None,
        **meta: Any,
    ) -> TaskResult:
        return cls(
            ok=True,
            output=output,
            data=data,
            run_id=run_id,
            usage=usage or TaskUsage(),
            metadata=meta,
        )

    @classmethod
    def failure(
        cls,
        error: str,
        *,
        run_id: str = "",
        usage: TaskUsage | None = None,
        **meta: Any,
    ) -> TaskResult:
        return cls(
            ok=False,
            error=error,
            run_id=run_id,
            usage=usage or TaskUsage(),
            metadata=meta,
        )
