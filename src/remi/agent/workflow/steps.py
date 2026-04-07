"""Step executors — one function per step kind.

Each executor takes a node config, the resolved inputs, and
infrastructure deps, and returns a ``StepResult``.

Step kinds:
  llm        — single LLM completion, no tools
  llm_tools  — LLM with tool access, bounded tool-call loop
  transform  — tool from ToolRegistry, no LLM
  for_each   — iterate over a list, run a tool per item
  gate       — evaluates a condition, returns pass/fail
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from pydantic import BaseModel, ValidationError

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
from remi.agent.types import ToolRegistry
from remi.agent.workflow.resolve import evaluate_condition, parse_json_output, resolve_template
from remi.agent.workflow.types import (
    ForEachNode,
    LLMNode,
    LLMToolsNode,
    OutputSchemaRegistry,
    StepResult,
    StepValue,
    TransformNode,
    WorkflowDefaults,
    WorkflowNode,
)

_log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------

ToolExecuteFn = Callable[[str, dict[str, Any]], Awaitable[Any]]
"""Async callable: (tool_name, arguments) -> result."""

# ---------------------------------------------------------------------------
# Output schema validation
# ---------------------------------------------------------------------------


def _validate_output(
    value: StepValue,
    schema_name: str,
    schema_registry: OutputSchemaRegistry,
    step_id: str,
) -> StepValue:
    """Validate step output against a Pydantic model if registered."""
    if not schema_name:
        return value
    schema_cls = schema_registry.get(schema_name)
    if schema_cls is None:
        _log.warning(
            "output_schema_not_registered",
            step=step_id,
            schema=schema_name,
        )
        return value
    if not isinstance(value, dict):
        raise ValueError(
            f"Step '{step_id}' output_schema='{schema_name}' expects dict, "
            f"got {type(value).__name__}"
        )
    schema_cls.model_validate(value)
    return value


# ---------------------------------------------------------------------------
# LLM step — single completion, no tools
# ---------------------------------------------------------------------------


async def run_llm_step(
    step: LLMNode,
    workflow_input: str,
    step_outputs: dict[str, StepValue],
    context: dict[str, str] | None,
    defaults: WorkflowDefaults,
    provider_factory: LLMProviderFactory,
    usage_ledger: LLMUsageLedger | None,
    schema_registry: OutputSchemaRegistry,
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
    _validate_output(value, step.output_schema, schema_registry, step.id)
    _record_usage(usage_ledger, step, provider_name, model, response, workflow_name)

    return StepResult(step_id=step.id, value=value, usage=response.usage)


# ---------------------------------------------------------------------------
# LLM + tools step — bounded tool-call loop
# ---------------------------------------------------------------------------


async def run_llm_tools_step(
    step: LLMToolsNode,
    workflow_input: str,
    step_outputs: dict[str, StepValue],
    context: dict[str, str] | None,
    defaults: WorkflowDefaults,
    provider_factory: LLMProviderFactory,
    usage_ledger: LLMUsageLedger | None,
    tool_definitions: list[ToolDefinition],
    tool_execute: ToolExecuteFn,
    schema_registry: OutputSchemaRegistry,
    *,
    workflow_name: str = "",
) -> StepResult:
    """Execute an LLM step with tool access."""
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
            _validate_output(value, step.output_schema, schema_registry, step.id)
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
    _validate_output(value, step.output_schema, schema_registry, step.id)
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
# Transform step — tool from ToolRegistry
# ---------------------------------------------------------------------------


async def run_transform_step(
    step: TransformNode,
    step_outputs: dict[str, StepValue],
    tool_registry: ToolRegistry,
    port_data: dict[str, Any] | None = None,
) -> StepResult:
    """Execute a tool from the shared registry as a transform step."""
    entry = tool_registry.get(step.tool)
    if entry is None:
        raise ValueError(
            f"Tool '{step.tool}' not found in registry. "
            f"Available: {[t.name for t in tool_registry.list_tools()]}"
        )
    tool_fn = entry[0]

    args: dict[str, Any] = {dep: step_outputs.get(dep, {}) for dep in step.depends_on}
    if port_data:
        args.update(port_data)

    result = await tool_fn(args)
    value: StepValue = result if isinstance(result, (str, list, dict)) else {"result": str(result)}
    return StepResult(step_id=step.id, value=value)


# ---------------------------------------------------------------------------
# For-each step — iterate over a list, run a tool per item
# ---------------------------------------------------------------------------


async def run_for_each_step(
    step: ForEachNode,
    step_outputs: dict[str, StepValue],
    tool_registry: ToolRegistry,
) -> StepResult:
    """Execute a tool for each item in a list from upstream output."""
    entry = tool_registry.get(step.tool)
    if entry is None:
        raise ValueError(
            f"Tool '{step.tool}' not found in registry. "
            f"Available: {[t.name for t in tool_registry.list_tools()]}"
        )
    tool_fn = entry[0]

    items = _resolve_items(step.items_from, step_outputs)
    if not isinstance(items, list):
        raise ValueError(
            f"ForEachNode '{step.id}' items_from='{step.items_from}' "
            f"resolved to {type(items).__name__}, expected list"
        )

    results: list[Any] = []
    errors: list[str] = []
    semaphore = asyncio.Semaphore(step.concurrency)

    async def _run_one(idx: int, item: Any) -> None:
        async with semaphore:
            try:
                r = await tool_fn(item if isinstance(item, dict) else {"item": item})
                results.append(r)
            except Exception as exc:
                if step.on_error == "abort":
                    raise
                _log.warning(
                    "for_each_item_error",
                    step=step.id,
                    index=idx,
                    error=str(exc),
                    exc_info=True,
                )
                errors.append(f"[{idx}] {exc}")

    if step.concurrency <= 1:
        for idx, item in enumerate(items):
            await _run_one(idx, item)
    else:
        tasks = [
            asyncio.create_task(_run_one(idx, item))
            for idx, item in enumerate(items)
        ]
        await asyncio.gather(*tasks)

    return StepResult(
        step_id=step.id,
        value={"results": results, "errors": errors, "total": len(items)},
        errors=errors,
    )


def _resolve_items(path: str, step_outputs: dict[str, StepValue]) -> Any:
    """Resolve a dot-path like ``steps.validate.accepted`` to a value."""
    if path.startswith("steps."):
        path = path[6:]

    parts = path.split(".")
    current: Any = step_outputs

    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
        if current is None:
            return None

    return current


# ---------------------------------------------------------------------------
# Gate step — conditional pass/fail
# ---------------------------------------------------------------------------


async def run_gate_step(
    step: WorkflowNode,
    step_outputs: dict[str, StepValue],
) -> StepResult:
    """Evaluate a gate condition against prior step outputs."""
    condition = getattr(step, "condition", "")
    passed = evaluate_condition(condition, step_outputs)
    return StepResult(
        step_id=step.id,
        value={"passed": passed},
        gated=not passed,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_messages(
    step: LLMNode | LLMToolsNode,
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
    step: LLMNode | LLMToolsNode,
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
