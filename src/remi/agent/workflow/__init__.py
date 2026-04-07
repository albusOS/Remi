"""agent/workflow — Pydantic-typed DAG workflow engine.

The canonical execution engine for all LLM workflows. Supports parallel
steps, tool-calling steps, gates, transforms, for-each iteration, typed
Pydantic node models, wire-based data routing, retry policies, output
schema validation, and structured execution events.

Workflows are loaded from YAML manifests via ``load_workflow(name)``.
Call ``set_agents_dir(path)`` at startup to configure the manifest root.

Public API::

    from remi.agent.workflow import WorkflowRunner, WorkflowResult, load_workflow
"""

from remi.agent.workflow.engine import WorkflowRunner
from remi.agent.workflow.loader import load_workflow, set_agents_dir
from remi.agent.workflow.plan import build_execution_plan
from remi.agent.workflow.resolve import evaluate_condition
from remi.agent.workflow.types import (
    BackoffStrategy,
    EventCallback,
    ExecutionPlan,
    ForEachNode,
    GateNode,
    InboundBinding,
    LLMNode,
    LLMToolsNode,
    NodeBase,
    NodeCompleted,
    NodeEvent,
    NodeFailed,
    NodeRetrying,
    NodeSkipped,
    NodeStarted,
    OutputSchemaRegistry,
    RetryPolicy,
    StepConfig,
    StepKind,
    StepResult,
    StepValue,
    TransformNode,
    Wire,
    WorkflowDef,
    WorkflowDefaults,
    WorkflowNode,
    WorkflowResult,
)

__all__ = [
    "BackoffStrategy",
    "EventCallback",
    "ExecutionPlan",
    "ForEachNode",
    "GateNode",
    "InboundBinding",
    "LLMNode",
    "LLMToolsNode",
    "NodeBase",
    "NodeCompleted",
    "NodeEvent",
    "NodeFailed",
    "NodeRetrying",
    "NodeSkipped",
    "NodeStarted",
    "OutputSchemaRegistry",
    "RetryPolicy",
    "StepConfig",
    "StepKind",
    "StepResult",
    "StepValue",
    "TransformNode",
    "Wire",
    "WorkflowDef",
    "WorkflowDefaults",
    "WorkflowNode",
    "WorkflowResult",
    "WorkflowRunner",
    "build_execution_plan",
    "evaluate_condition",
    "load_workflow",
    "set_agents_dir",
]
