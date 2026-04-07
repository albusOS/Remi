"""Step executors — one function per step kind.

Each executor takes a ``StepConfig``, the resolved inputs, and
infrastructure deps, and returns a ``StepResult``.

Step kinds:
  llm        — single LLM completion, no tools
  llm_tools  — LLM with tool access, bounded tool-call loop
  transform  — pure Python callable, no LLM
  gate       — evaluates a condition, returns pass/fail
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

import structlog

from remi.agent.llm.factory import LLMProviderFactory
from remi.agent.llm.types import (
    LLMResponse,
    Message,
    TokenUsage,
    ToolCallRequest,
    ToolDefinition,
    estimate_cost,
)
from remi.agent.observe.usage import LLMUsageLedger, UsageRecord, UsageSource
from remi.agent.workflow.resolve import parse_json_output, resolve_template
from remi.agent.workflow.types import StepConfig, StepResult, StepValue, WorkflowDefaults

_log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------

ToolExecuteFn = Callable[[str, dict[str, Any]], Awaitable[Any]]
"""Async callable: (tool_name, arguments) -> result."""

TransformFn = Callable[[dict[str, StepValue]], Awaitable[StepValue] | StepValue]
"""Registered Python transform: step_outputs -> merged value."""

TransformRegistry = dict[str, TransformFn]


# ---------------------------------------------------------------------------
# LLM step — single completion, no tools
# ---------------------------------------------------------------------------


async def run_llm_step(
    step: StepConfig,
    workflow_input: str,
    step_outputs: dict[str, StepValue],
    context: dict[str, str] | None,
    defaults: WorkflowDefaults,
    provider_factory: LLMProviderFactory,
    usage_ledger: LLMUsageLedger | None,
    *,
    workflow_name: str = "",
) -> StepResult:
    """Execute a single LLM completion step."""
    provider_name = step.provider or defaults.provider
    model = step.model or defaults.model
    provider = provider_factory.create(provider_name)

    messages = _build_messages(step, workflow_input, step_outputs, context)

    response = await provider.complete(
        model=model,
        messages=messages,
        temperature=step.temperature,
        max_tokens=step.max_tokens,
    )

    value = _extract_value(response, step.response_format)
    _record_usage(usage_ledger, step, provider_name, model, response, workflow_name)

    return StepResult(step_id=step.id, value=value, usage=response.usage)


# ---------------------------------------------------------------------------
# LLM + tools step — bounded tool-call loop
# ---------------------------------------------------------------------------


async def run_llm_tools_step(
    step: StepConfig,
    workflow_input: str,
    step_outputs: dict[str, StepValue],
    context: dict[str, str] | None,
    defaults: WorkflowDefaults,
    provider_factory: LLMProviderFactory,
    usage_ledger: LLMUsageLedger | None,
    tool_definitions: list[ToolDefinition],
    tool_execute: ToolExecuteFn,
    *,
    workflow_name: str = "",
) -> StepResult:
    """Execute an LLM step with tool access.

    Runs a tight tool-call loop: the LLM can call tools up to
    ``step.max_tool_rounds`` times, then must produce a final response.
    No scratchpad, no phases, no workspace — just think-act-observe.
    """
    provider_name = step.provider or defaults.provider
    model = step.model or defaults.model
    provider = provider_factory.create(provider_name)

    thread = _build_messages(step, workflow_input, step_outputs, context)
    run_usage = TokenUsage()
    rounds_remaining = step.max_tool_rounds + 1

    while rounds_remaining > 0:
        rounds_remaining -= 1
        budget_spent = rounds_remaining == 0
        active_tools = None if budget_spent else (tool_definitions or None)

        response = await provider.complete(
            model=model,
            messages=thread,
            temperature=step.temperature,
            max_tokens=step.max_tokens,
            tools=active_tools,
        )
        run_usage = run_usage + response.usage
        _record_usage(usage_ledger, step, provider_name, model, response, workflow_name)

        if not response.tool_calls:
            value = _extract_value(response, step.response_format)
            return StepResult(step_id=step.id, value=value, usage=run_usage)

        thread.append(
            Message(
                role="assistant",
                content=response.content or "",
                tool_calls=response.tool_calls,
            )
        )

        tool_messages = await asyncio.gather(
            *[_execute_tool(tc, tool_execute, step.id) for tc in response.tool_calls]
        )
        thread.extend(tool_messages)

    value = _extract_value(response, step.response_format)
    return StepResult(step_id=step.id, value=value, usage=run_usage)


async def _execute_tool(
    tc: ToolCallRequest,
    execute_fn: ToolExecuteFn,
    step_id: str,
) -> Message:
    """Execute a single tool call and return the tool Message."""
    _log.info("workflow_tool_call", step=step_id, tool=tc.name, call_id=tc.id)
    try:
        result = await execute_fn(tc.name, tc.arguments)
    except Exception as exc:
        _log.error(
            "workflow_tool_error",
            step=step_id,
            tool=tc.name,
            error=str(exc),
            exc_info=True,
        )
        result = {"error": str(exc)}

    content = result if isinstance(result, str) else json.dumps(result, default=str)
    return Message(role="tool", name=tc.name, tool_call_id=tc.id, content=content)


# ---------------------------------------------------------------------------
# Transform step — pure Python callable
# ---------------------------------------------------------------------------


async def run_transform_step(
    step: StepConfig,
    step_outputs: dict[str, StepValue],
    transform_registry: TransformRegistry,
) -> StepResult:
    """Execute a registered Python transform."""
    fn = transform_registry.get(step.transform)
    if fn is None:
        raise ValueError(
            f"Transform '{step.transform}' not registered. "
            f"Available: {list(transform_registry.keys())}"
        )

    upstream = {dep: step_outputs.get(dep, {}) for dep in step.depends_on}
    result = fn(upstream)
    if asyncio.iscoroutine(result):
        result = await result
    return StepResult(step_id=step.id, value=result)


# ---------------------------------------------------------------------------
# Gate step — conditional pass/fail
# ---------------------------------------------------------------------------


async def run_gate_step(
    step: StepConfig,
    step_outputs: dict[str, StepValue],
) -> StepResult:
    """Evaluate a gate condition against prior step outputs.

    Condition syntax is intentionally simple — just dot-path truthiness
    checks against step outputs:
      - ``steps.extract.has_proposals``  →  step_outputs["extract"]["has_proposals"]
      - ``steps.classify``               →  bool(step_outputs["classify"])

    Returns a StepResult where ``gated=True`` means the condition FAILED
    and downstream steps should be skipped.
    """
    passed = _evaluate_condition(step.condition, step_outputs)
    return StepResult(
        step_id=step.id,
        value={"passed": passed},
        gated=not passed,
    )


def _evaluate_condition(condition: str, step_outputs: dict[str, StepValue]) -> bool:
    """Evaluate a simple dot-path condition against step outputs."""
    if not condition:
        return True

    path = condition.strip()

    # Strip optional "steps." prefix
    if path.startswith("steps."):
        path = path[6:]

    parts = path.split(".", 1)
    step_id = parts[0]
    value = step_outputs.get(step_id)

    if value is None:
        return False

    if len(parts) == 1:
        return bool(value)

    field = parts[1]
    if isinstance(value, dict):
        return bool(value.get(field))

    return bool(value)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_messages(
    step: StepConfig,
    workflow_input: str,
    step_outputs: dict[str, StepValue],
    context: dict[str, str] | None,
) -> list[Message]:
    """Build the LLM message list for a step."""
    messages: list[Message] = []
    if step.system_prompt:
        resolved_system = resolve_template(
            step.system_prompt,
            workflow_input,
            step_outputs,
            context,
        )
        messages.append(Message(role="system", content=resolved_system))

    user_content = resolve_template(
        step.input_template,
        workflow_input,
        step_outputs,
        context,
    )
    messages.append(Message(role="user", content=user_content))
    return messages


def _extract_value(response: LLMResponse, response_format: str) -> StepValue:
    """Pull the value out of an LLM response."""
    raw = response.content or ""
    if response_format == "json":
        return parse_json_output(raw)
    return raw


def _record_usage(
    ledger: LLMUsageLedger | None,
    step: StepConfig,
    provider_name: str,
    model: str,
    response: LLMResponse,
    workflow_name: str,
) -> None:
    """Record token usage if a ledger is available."""
    if ledger is None or response.usage.total_tokens == 0:
        return
    cost = estimate_cost(model, response.usage.prompt_tokens, response.usage.completion_tokens)
    ledger.record(
        UsageRecord(
            source=UsageSource.INGESTION,
            source_detail=f"{workflow_name}:{step.id}" if workflow_name else step.id,
            provider=provider_name,
            model=model,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
            cache_read_tokens=response.usage.cache_read_tokens,
            cache_creation_tokens=response.usage.cache_creation_tokens,
            estimated_cost_usd=round(cost, 6) if cost is not None else None,
        )
    )
