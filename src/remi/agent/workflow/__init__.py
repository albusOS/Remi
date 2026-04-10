"""agent/workflow — Pydantic-typed DAG workflow engine.

The canonical execution engine for all LLM workflows. Supports parallel
steps, tool-calling steps, gates, transforms, for-each iteration, typed
Pydantic node models, wire-based data routing, retry policies, output
schema validation, and structured execution events.

Workflows are loaded from YAML manifests via ``load_workflow(name)``.
Register manifests at startup with ``register_manifest(name, path)``.

Public API::

    from remi.agent.workflow import WorkflowRunner, WorkflowResult, load_workflow
"""

from remi.agent.workflow.engine import WorkflowRunner
from remi.agent.workflow.loader import load_manifest_runtime, load_workflow
from remi.agent.workflow.plan import build_execution_plan
from remi.agent.workflow.registry import (
    ManifestRegistry,
    all_manifests,
    get_manifest_kind,
    get_manifest_path,
    register_manifest,
)
from remi.agent.workflow.resolve import evaluate_condition
from remi.agent.workflow.types import (
    AgentStepNode,
    BackoffStrategy,
    ContextMode,
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
    "AgentStepNode",
    "BackoffStrategy",
    "ContextMode",
    "EventCallback",
    "ExecutionPlan",
    "ForEachNode",
    "GateNode",
    "InboundBinding",
    "LLMNode",
    "LLMToolsNode",
    "ManifestRegistry",
    "NodeBase",
    "NodeCompleted",
    "NodeEvent",
    "NodeFailed",
    "NodeRetrying",
    "NodeSkipped",
    "NodeStarted",
    "OutputSchemaRegistry",
    "RetryPolicy",
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
    "all_manifests",
    "build_execution_plan",
    "evaluate_condition",
    "get_manifest_kind",
    "get_manifest_path",
    "load_manifest_runtime",
    "load_workflow",
    "register_manifest",
]
