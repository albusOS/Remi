"""Query fast path — data injection + single LLM formatting call.

Handles Tier.QUERY requests without entering the agent loop.  The
router has already classified the question and identified the operation.
This module:

1. Calls a ``DataResolver`` to fetch data in-process (sub-10ms)
2. Injects the data into a single LLM completion (no tools)
3. Returns the formatted answer

Zero tool calls.  Zero subprocess overhead.  One LLM round-trip.

Domain-agnostic: the ``DataResolver`` protocol is implemented by the
application layer.  This module knows nothing about real estate.
"""

from __future__ import annotations

import json
import time
from typing import Any, Protocol

import structlog

from remi.agent.llm.types import LLMProvider, Message

logger = structlog.get_logger(__name__)


class DataResolver(Protocol):
    """Protocol for the data-fetch backend.

    Implemented in the application layer, injected via the container.
    The runtime depends only on this protocol.
    """

    async def resolve(
        self,
        operation: str,
        params: dict[str, str],
    ) -> dict[str, Any]: ...


async def run_query_path(
    *,
    question: str,
    operation: str,
    params: dict[str, str],
    resolver: DataResolver,
    provider: LLMProvider,
    model: str,
    system_preamble: str = "",
    on_event: Any | None = None,
) -> tuple[str, dict[str, Any]]:
    """Fetch data, format with one LLM call, return answer + metadata.

    ``system_preamble`` is an optional domain-specific system prompt
    prefix injected by the application layer.

    Returns ``(answer_text, metadata_dict)``.
    """
    t0 = time.monotonic()
    emit = on_event or _noop

    data = await resolver.resolve(operation, params)
    resolve_ms = round((time.monotonic() - t0) * 1000)

    data_json = json.dumps(data, default=str, indent=2)
    if len(data_json) > 30_000:
        data_json = data_json[:30_000] + "\n... (truncated)"

    system = system_preamble or (
        "You have been given data that answers the user's question. "
        "Interpret the data and respond naturally. Be concise."
    )

    messages: list[Message] = [
        Message(role="system", content=system),
        Message(
            role="system",
            content=f"## Data ({operation})\n\n```json\n{data_json}\n```",
        ),
        Message(role="user", content=question),
    ]

    response = await provider.complete(
        model=model,
        messages=messages,
        temperature=0.3,
        max_tokens=4096,
    )

    answer = response.content or ""
    total_ms = round((time.monotonic() - t0) * 1000)

    metadata: dict[str, Any] = {
        "tier": "query",
        "operation": operation,
        "resolve_ms": resolve_ms,
        "latency_ms": total_ms,
        "model": model,
        "usage": {
            "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
            "completion_tokens": response.usage.completion_tokens if response.usage else 0,
        },
    }

    await emit("done", metadata)

    logger.info(
        "query_path_done",
        operation=operation,
        resolve_ms=resolve_ms,
        latency_ms=total_ms,
        model=model,
    )

    return answer, metadata


async def _noop(_type: str, _data: dict[str, Any]) -> None:
    pass
