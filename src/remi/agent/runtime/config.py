"""Runtime configuration — declarative execution topology for agents and workflows.

These types define the ``runtime:`` section of app.yaml manifests. They
control *how* an agent or workflow runs — placement, isolation, durability,
and resource budgets — independent of *what* it does.

The same agent YAML can run inline (single process), on a worker pool
(Redis-backed task queue), or in an isolated container, depending on
these settings. Defaults are always safe for single-process dev.

Example YAML::

    runtime:
      placement: worker         # inline | worker | container
      isolation: sandbox        # none | sandbox | container
      durability: ephemeral     # ephemeral | checkpoint | durable
      resources:
        timeout_seconds: 120
        max_memory_mb: 2048
        max_tool_rounds: 20
        max_tokens: 200000
      scaling:
        max_concurrency: 2
        queue_priority: normal  # low | normal | high | critical
"""

from __future__ import annotations

from enum import StrEnum, unique
from typing import Any

from pydantic import BaseModel, ConfigDict


@unique
class Placement(StrEnum):
    """Where the agent loop executes relative to the API process.

    INLINE — same process, same event loop. Lowest latency, no isolation.
             Required for streaming chat (director). Default.
    WORKER — dispatched to a task queue, executed by a worker process.
             Decouples API latency from agent execution cost.
    CONTAINER — each run gets its own container/sandbox. Full isolation.
                Highest latency, strongest resource guarantees.
    SERVICE — agent runs as its own long-lived HTTP service.
              Independently deployable. ``endpoint`` must be set.
    """

    INLINE = "inline"
    WORKER = "worker"
    CONTAINER = "container"
    SERVICE = "service"


@unique
class Isolation(StrEnum):
    """How tightly the agent is sandboxed.

    NONE — agent tools run in the host process. Fastest.
    SANDBOX — code execution tools (python/bash) run in a sandbox;
              other tools run in-process. Current default behavior.
    CONTAINER — the entire agent runtime runs in an isolated container.
                All tools are network-isolated.
    """

    NONE = "none"
    SANDBOX = "sandbox"
    CONTAINER = "container"


@unique
class Durability(StrEnum):
    """State persistence guarantees for the execution.

    EPHEMERAL — state lost on crash. Fine for chat, lookups.
    CHECKPOINT — periodic checkpoints to external storage.
                 Resume from last checkpoint on failure.
    DURABLE — every step is persisted. Guaranteed completion
              even across process restarts. Requires a durable
              execution backend (Temporal, Redis+Postgres).
    """

    EPHEMERAL = "ephemeral"
    CHECKPOINT = "checkpoint"
    DURABLE = "durable"


@unique
class QueuePriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class ResourceBudget(BaseModel):
    """Hard resource limits enforced by the runtime."""

    model_config = ConfigDict(frozen=True)

    timeout_seconds: float | None = None
    max_memory_mb: int | None = None
    max_tool_rounds: int | None = None
    max_tokens: int | None = None


class ScalingConfig(BaseModel):
    """Concurrency and priority settings for queued execution."""

    model_config = ConfigDict(frozen=True)

    max_concurrency: int = 1
    queue_priority: QueuePriority = QueuePriority.NORMAL


class RuntimeConfig(BaseModel):
    """Declarative execution topology for an agent or workflow.

    Parsed from the ``runtime:`` section of app.yaml. Every field has a
    sensible default so omitting ``runtime:`` entirely gives you the
    current single-process behavior.

    ``endpoint`` is the base URL when ``placement: service`` — the agent
    runs as its own HTTP service at this address. Ignored for other placements.
    """

    model_config = ConfigDict(frozen=True)

    placement: Placement = Placement.INLINE
    isolation: Isolation = Isolation.SANDBOX
    durability: Durability = Durability.EPHEMERAL
    resources: ResourceBudget = ResourceBudget()
    scaling: ScalingConfig = ScalingConfig()
    endpoint: str = ""

    def to_task_constraints(self) -> dict[str, Any]:
        """Export resource limits in the shape TaskConstraints expects."""
        constraints: dict[str, Any] = {}
        if self.resources.timeout_seconds is not None:
            constraints["timeout_seconds"] = self.resources.timeout_seconds
        if self.resources.max_tool_rounds is not None:
            constraints["max_tool_rounds"] = self.resources.max_tool_rounds
        if self.resources.max_tokens is not None:
            constraints["max_tokens"] = self.resources.max_tokens
        return constraints
