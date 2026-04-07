"""agent/workflow — DAG-based structured LLM workflow engine.

Replaces ``agent/pipeline/`` with a proper execution engine that supports
parallel steps, tool-calling steps, gates, and transforms.

Workflows are defined in ``application/agents/<name>/app.yaml`` with
``kind: Workflow`` (or ``kind: Pipeline`` for backward compat).

Public API::

    from remi.agent.workflow import WorkflowRunner, WorkflowResult, load_workflow
"""

from remi.agent.workflow.engine import WorkflowRunner
from remi.agent.workflow.loader import load_workflow
from remi.agent.workflow.types import (
    StepConfig,
    StepKind,
    StepResult,
    WorkflowDef,
    WorkflowDefaults,
    WorkflowResult,
)

__all__ = [
    "StepConfig",
    "StepKind",
    "StepResult",
    "WorkflowDef",
    "WorkflowDefaults",
    "WorkflowResult",
    "WorkflowRunner",
    "load_workflow",
]
