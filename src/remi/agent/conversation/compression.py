"""Tool result compression — keeps the agent thread lean.

Large tool results (workflow reviews, HTTP responses, delegation output)
are compressed before being appended to the thread.  This prevents
quadratic token growth when the agent makes multiple tool calls:
each subsequent LLM call re-reads the *entire* thread, so a 5K-token
tool result read 10 times costs 50K tokens of pure waste.

Strategy:
- Results under the token threshold pass through unchanged.
- Over the threshold: extract a structured summary (top-level keys,
  row counts, numeric aggregates) and truncate the raw payload.
  The summary preserves enough signal for the LLM to reason without
  needing the full JSON.
- When a MemoryStore is available (offload path): full payload is
  written to the store under a deterministic key; only the summary +
  a retrieval reference is kept in the thread.  The agent can re-read
  via ``memory_recall``.  This is the "context = RAM, store = disk"
  pattern from Manus.
"""

from __future__ import annotations

import json
from typing import Any

from remi.agent.graph.stores import MemoryStore

_TOKEN_THRESHOLD = 500
_OFFLOAD_THRESHOLD = 1500
_CHARS_PER_TOKEN = 4
_MAX_SUMMARY_CHARS = 1600


def _estimate_tokens(text: str) -> int:
    return len(text) // _CHARS_PER_TOKEN


def compress_tool_result(tool_name: str, result: Any) -> Any:
    """Compress a tool result if it exceeds the token budget.

    Returns the original result if small enough, or a compact summary
    dict with key metrics preserved and the raw payload truncated.
    """
    if isinstance(result, str):
        if _estimate_tokens(result) <= _TOKEN_THRESHOLD:
            return result
        return _truncate_string(result)

    if isinstance(result, (int, float, bool)) or result is None:
        return result

    serialized = json.dumps(result, default=str)
    if _estimate_tokens(serialized) <= _TOKEN_THRESHOLD:
        return result

    return _summarize_structured(tool_name, result, serialized)


async def compress_and_offload(
    tool_name: str,
    call_id: str,
    result: Any,
    memory: MemoryStore | None,
    namespace: str,
) -> Any:
    """Compress a tool result, offloading large payloads to MemoryStore.

    When *memory* is available and the result exceeds the offload
    threshold, the full payload is persisted under a deterministic key
    and a compact summary with a retrieval hint replaces it in the
    thread.  The agent can fetch the full data via ``memory_recall``.

    Falls back to ``compress_tool_result`` when no store is available
    or when the result is small enough.
    """
    if isinstance(result, (str, int, float, bool)) or result is None:
        return compress_tool_result(tool_name, result)

    serialized = json.dumps(result, default=str)
    tokens = _estimate_tokens(serialized)

    if tokens <= _TOKEN_THRESHOLD:
        return result

    if memory is None or tokens < _OFFLOAD_THRESHOLD:
        return _summarize_structured(tool_name, result, serialized)

    offload_key = f"tool:{call_id}"
    await memory.store(namespace, offload_key, serialized, ttl=3600)

    summary = _summarize_structured(tool_name, result, serialized)
    summary["_offloaded"] = True
    summary["_recall_key"] = offload_key
    summary["_recall_hint"] = (
        f"Full {tokens}-token result saved. "
        f'Retrieve with memory_recall(key="{offload_key}") if you need the complete data.'
    )
    return summary


def _truncate_string(text: str) -> str:
    limit = _TOKEN_THRESHOLD * _CHARS_PER_TOKEN
    return text[:limit] + f"\n\n[Truncated — {len(text)} chars total, showing first {limit}]"


def _summarize_structured(tool_name: str, result: Any, serialized: str) -> dict[str, Any]:
    """Build a compact summary of a large structured result."""
    summary: dict[str, Any] = {
        "_compressed": True,
        "_tool": tool_name,
        "_original_tokens": _estimate_tokens(serialized),
    }

    if isinstance(result, list):
        summary["_count"] = len(result)
        if result and isinstance(result[0], dict):
            summary["_keys"] = list(result[0].keys())
            summary["items"] = _extract_list_summary(result)
        else:
            summary["items"] = result[:5]
        return summary

    if isinstance(result, dict):
        if "error" in result:
            return result

        summary["_keys"] = list(result.keys())
        compressed_body: dict[str, Any] = {}

        for key, value in result.items():
            compressed_body[key] = _compress_value(key, value)

        summary["data"] = compressed_body
        return summary

    return summary


def _compress_value(key: str, value: Any) -> Any:
    """Compress a single value within a dict result."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    if isinstance(value, list):
        if not value:
            return []
        count = len(value)
        if count <= 3:
            return value
        if isinstance(value[0], dict):
            preview = _extract_list_summary(value, max_items=3)
            return {"_count": count, "_preview": preview}
        return {"_count": count, "_preview": value[:3]}

    if isinstance(value, dict):
        text = json.dumps(value, default=str)
        if _estimate_tokens(text) <= 100:
            return value
        scalars = {
            k: v for k, v in value.items() if isinstance(v, (str, int, float, bool)) or v is None
        }
        nested_summaries = {
            k: f"[{type(v).__name__}: {len(v)} items]"
            for k, v in value.items()
            if isinstance(v, (list, dict)) and k not in scalars
        }
        return {**scalars, **nested_summaries}

    return str(value)[:200]


def _extract_list_summary(items: list[dict[str, Any]], max_items: int = 5) -> list[dict[str, Any]]:
    """Extract the most informative fields from a list of dicts."""
    if not items:
        return []

    sample = items[:max_items]
    all_keys = list(items[0].keys())

    priority_keys = [
        k
        for k in all_keys
        if any(
            term in k.lower()
            for term in (
                "id",
                "name",
                "total",
                "balance",
                "rate",
                "count",
                "amount",
                "status",
                "score",
                "rank",
                "date",
            )
        )
    ]
    other_scalar_keys = [
        k
        for k in all_keys
        if k not in priority_keys and isinstance(items[0].get(k), (str, int, float, bool))
    ]
    keep_keys = (priority_keys + other_scalar_keys)[:12]

    if not keep_keys:
        keep_keys = all_keys[:8]

    return [{k: item.get(k) for k in keep_keys} for item in sample]
