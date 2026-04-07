"""Workflow engine — DAG scheduler with parallel step execution.

Builds a dependency graph from ``StepConfig.depends_on``, identifies
independent steps that can run concurrently, and dispatches them through
an ``asyncio.Semaphore`` to cap parallel LLM calls.

Gate steps propagate downward: if a gate fails, all transitive
dependents are skipped without execution.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict

import structlog

from remi.agent.llm.factory import LLMProviderFactory
from remi.agent.llm.types import ToolDefinition
from remi.agent.observe.usage import LLMUsageLedger
from remi.agent.workflow.steps import (
    ToolExecuteFn,
    TransformRegistry,
    run_gate_step,
    run_llm_step,
    run_llm_tools_step,
    run_transform_step,
)
from remi.agent.workflow.types import (
    StepConfig,
    StepKind,
    StepResult,
    StepValue,
    WorkflowDef,
    WorkflowDefaults,
    WorkflowResult,
)

_log = structlog.get_logger(__name__)


class WorkflowRunner:
    """Executes workflow DAGs with parallel scheduling.

    Construction requires the LLM factory and usage ledger. Tool
    definitions and transforms are passed per-run since they may vary
    by workflow.
    """

    def __init__(
        self,
        provider_factory: LLMProviderFactory,
        default_provider: str,
        default_model: str,
        usage_ledger: LLMUsageLedger | None = None,
    ) -> None:
        self._factory = provider_factory
        self._default_provider = default_provider
        self._default_model = default_model
        self._usage_ledger = usage_ledger

    async def run(
        self,
        workflow: WorkflowDef,
        workflow_input: str,
        *,
        context: dict[str, str] | None = None,
        skip_steps: set[str] | None = None,
        tool_definitions: list[ToolDefinition] | None = None,
        tool_execute: ToolExecuteFn | None = None,
        transforms: TransformRegistry | None = None,
    ) -> WorkflowResult:
        """Execute the workflow and return accumulated results."""
        skip = skip_steps or set()
        transforms = transforms or {}

        defaults = workflow.defaults
        if not defaults.provider:
            defaults = type(defaults)(
                provider=self._default_provider,
                model=defaults.model or self._default_model,
                max_concurrency=defaults.max_concurrency,
            )
        elif not defaults.model:
            defaults = type(defaults)(
                provider=defaults.provider,
                model=self._default_model,
                max_concurrency=defaults.max_concurrency,
            )

        adjacency, in_degree = _build_graph(workflow)
        semaphore = asyncio.Semaphore(defaults.max_concurrency)

        step_outputs: dict[str, StepValue] = {}
        step_results: dict[str, StepResult] = {}
        gated_steps: set[str] = set()
        completion_events: dict[str, asyncio.Event] = {
            s.id: asyncio.Event() for s in workflow.steps
        }

        _log.info(
            "workflow_start",
            workflow=workflow.name,
            step_count=len(workflow.steps),
            skipped=list(skip) if skip else [],
            max_concurrency=defaults.max_concurrency,
        )

        async def execute_step(step_id: str) -> None:
            step = workflow.get_step(step_id)
            if step is None:
                return

            # Wait for all dependencies to complete
            for dep in step.depends_on:
                await completion_events[dep].wait()

            # Check if any dependency was gated
            if any(dep in gated_steps for dep in step.depends_on):
                gated_steps.add(step_id)
                sr = StepResult(step_id=step_id, value={}, gated=True)
                step_results[step_id] = sr
                step_outputs[step_id] = {}
                _log.info("workflow_step_gated", workflow=workflow.name, step=step_id)
                completion_events[step_id].set()
                return

            # Check if explicitly skipped
            if step_id in skip:
                sr = StepResult(step_id=step_id, value={}, skipped=True)
                step_results[step_id] = sr
                step_outputs[step_id] = {}
                _log.info("workflow_step_skipped", workflow=workflow.name, step=step_id)
                completion_events[step_id].set()
                return

            async with semaphore:
                _log.info(
                    "workflow_step_start",
                    workflow=workflow.name,
                    step=step_id,
                    kind=step.kind,
                )
                sr = await _dispatch_step(
                    step=step,
                    workflow_input=workflow_input,
                    step_outputs=step_outputs,
                    context=context,
                    defaults=defaults,
                    provider_factory=self._factory,
                    usage_ledger=self._usage_ledger,
                    tool_definitions=tool_definitions,
                    tool_execute=tool_execute,
                    transforms=transforms,
                    workflow_name=workflow.name,
                )

            step_results[step_id] = sr
            step_outputs[step_id] = sr.value

            if sr.gated:
                gated_steps.add(step_id)

            _log.info(
                "workflow_step_done",
                workflow=workflow.name,
                step=step_id,
                kind=step.kind,
                gated=sr.gated,
                prompt_tokens=sr.usage.prompt_tokens,
                completion_tokens=sr.usage.completion_tokens,
            )
            completion_events[step_id].set()

        # Launch all steps concurrently — they self-synchronize via events
        tasks = [asyncio.create_task(execute_step(s.id)) for s in workflow.steps]

        # Gather and propagate any step-level exceptions
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, BaseException):
                step_id = workflow.steps[i].id
                _log.error(
                    "workflow_step_failed",
                    workflow=workflow.name,
                    step=step_id,
                    error=str(result),
                    exc_info=result,
                )
                # Unblock anything waiting on this step
                if not completion_events[step_id].is_set():
                    gated_steps.add(step_id)
                    step_outputs[step_id] = {}
                    completion_events[step_id].set()

        # Assemble final result in definition order
        wf_result = WorkflowResult()
        for step in workflow.steps:
            if step.id in step_results:
                sr = step_results[step.id]
                wf_result.steps.append(sr)
                wf_result.total_usage = wf_result.total_usage + sr.usage

        _log.info(
            "workflow_done",
            workflow=workflow.name,
            total_prompt_tokens=wf_result.total_usage.prompt_tokens,
            total_completion_tokens=wf_result.total_usage.completion_tokens,
            steps_completed=len(wf_result.steps),
            steps_gated=len(gated_steps),
        )
        return wf_result


# ---------------------------------------------------------------------------
# DAG construction
# ---------------------------------------------------------------------------


def _build_graph(
    workflow: WorkflowDef,
) -> tuple[dict[str, list[str]], dict[str, int]]:
    """Build adjacency list and in-degree map from step dependencies.

    Returns (adjacency, in_degree) where adjacency[A] = [B, C] means
    A is a dependency of B and C.
    """
    adjacency: dict[str, list[str]] = defaultdict(list)
    in_degree: dict[str, int] = {s.id: 0 for s in workflow.steps}
    valid_ids = workflow.step_ids()

    for step in workflow.steps:
        for dep in step.depends_on:
            if dep not in valid_ids:
                raise ValueError(
                    f"Step '{step.id}' depends on '{dep}' which does not exist "
                    f"in workflow '{workflow.name}'"
                )
            adjacency[dep].append(step.id)
            in_degree[step.id] += 1

    # Cycle detection via Kahn's algorithm
    queue = [sid for sid, deg in in_degree.items() if deg == 0]
    visited = 0
    temp_degree = dict(in_degree)
    while queue:
        node = queue.pop(0)
        visited += 1
        for child in adjacency[node]:
            temp_degree[child] -= 1
            if temp_degree[child] == 0:
                queue.append(child)

    if visited != len(workflow.steps):
        raise ValueError(f"Cycle detected in workflow '{workflow.name}'")

    return adjacency, in_degree


# ---------------------------------------------------------------------------
# Step dispatch
# ---------------------------------------------------------------------------


async def _dispatch_step(
    *,
    step: StepConfig,
    workflow_input: str,
    step_outputs: dict[str, StepValue],
    context: dict[str, str] | None,
    defaults: WorkflowDefaults,
    provider_factory: LLMProviderFactory,
    usage_ledger: LLMUsageLedger | None,
    tool_definitions: list[ToolDefinition] | None,
    tool_execute: ToolExecuteFn | None,
    transforms: TransformRegistry,
    workflow_name: str,
) -> StepResult:
    """Route a step to its executor based on kind."""

    if step.kind == StepKind.LLM:
        return await run_llm_step(
            step,
            workflow_input,
            step_outputs,
            context,
            defaults,
            provider_factory,
            usage_ledger,
            workflow_name=workflow_name,
        )

    if step.kind == StepKind.LLM_TOOLS:
        if tool_execute is None:
            raise ValueError(f"Step '{step.id}' is kind=llm_tools but no tool_execute was provided")
        # Filter tool definitions to only the tools this step declared
        step_tool_names = set(step.tools)
        if step_tool_names and tool_definitions:
            filtered_defs = [td for td in tool_definitions if td.name in step_tool_names]
        else:
            filtered_defs = tool_definitions or []

        return await run_llm_tools_step(
            step,
            workflow_input,
            step_outputs,
            context,
            defaults,
            provider_factory,
            usage_ledger,
            filtered_defs,
            tool_execute,
            workflow_name=workflow_name,
        )

    if step.kind == StepKind.TRANSFORM:
        return await run_transform_step(step, step_outputs, transforms)

    if step.kind == StepKind.GATE:
        return await run_gate_step(step, step_outputs)

    raise ValueError(f"Unknown step kind: {step.kind}")
