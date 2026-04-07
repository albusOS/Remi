"""Multi-stage context compaction — prevents context window overflow.

Three stages, applied when the thread approaches the token budget:

1. **Tool result compression** — already handled by ``compression.py``
   on a per-tool-call basis.  Not invoked here.

2. **Exchange summarization** — groups old exchanges into batches and
   replaces each batch with a short LLM-generated summary.  Preserves
   system prefix and recent exchanges.

3. **Aggressive compaction** — when summarization isn't enough, collapse
   everything except the system prefix and recent exchanges into a
   single "session so far" summary.

The loop calls ``should_compact`` before each LLM call.  If compaction
is needed, it runs the appropriate stage and continues.
"""

from __future__ import annotations

import enum
import json

import structlog

from remi.agent.llm.types import LLMProvider, LLMRequest, Message

logger = structlog.get_logger(__name__)

_CHARS_PER_TOKEN = 4

_SUMMARIZE_THRESHOLD = 0.70
_COMPACT_THRESHOLD = 0.88

_RECENT_EXCHANGES_TO_KEEP = 3

_SUMMARIZE_SYSTEM = """\
Summarize the following conversation exchanges into 2-3 concise sentences. \
Preserve key findings, decisions, entity names, and numbers. \
Do not include tool call details unless the result was important. \
Output only the summary text."""

_COMPACT_SYSTEM = """\
Summarize everything that happened in this agent session so far into a \
concise briefing (3-5 sentences). Preserve: key findings, decisions made, \
entities analyzed, corrections received, and any unfinished plan. \
Output only the summary text."""


class CompactionLevel(enum.Enum):
    NONE = "none"
    SUMMARIZE = "summarize"
    COMPACT = "compact"


def estimate_thread_tokens(thread: list[Message]) -> int:
    """Estimate the token count of a thread."""
    total = 0
    for msg in thread:
        content = msg.content
        if isinstance(content, dict):
            content = json.dumps(content, default=str)
        elif not isinstance(content, str):
            content = str(content) if content else ""
        total += len(content) // _CHARS_PER_TOKEN + 4
    return total


def should_compact(thread: list[Message], context_budget: int) -> CompactionLevel:
    """Determine whether compaction is needed based on current thread size."""
    if context_budget <= 0:
        return CompactionLevel.NONE

    used = estimate_thread_tokens(thread)
    ratio = used / context_budget

    if ratio >= _COMPACT_THRESHOLD:
        return CompactionLevel.COMPACT
    if ratio >= _SUMMARIZE_THRESHOLD:
        return CompactionLevel.SUMMARIZE
    return CompactionLevel.NONE


def _split_thread(
    thread: list[Message],
) -> tuple[list[Message], list[list[Message]], list[list[Message]]]:
    """Split thread into (system_prefix, old_exchanges, recent_exchanges)."""
    system_prefix: list[Message] = []
    conversation: list[Message] = []
    for msg in thread:
        if not conversation and msg.role == "system":
            system_prefix.append(msg)
        else:
            conversation.append(msg)

    exchanges: list[list[Message]] = []
    current: list[Message] = []
    for msg in conversation:
        if msg.role == "user" and current:
            exchanges.append(current)
            current = []
        current.append(msg)
    if current:
        exchanges.append(current)

    keep = min(_RECENT_EXCHANGES_TO_KEEP, len(exchanges))
    old = exchanges[: len(exchanges) - keep] if keep < len(exchanges) else []
    recent = exchanges[len(exchanges) - keep :] if keep > 0 else exchanges

    return system_prefix, old, recent


def _exchanges_to_text(exchanges: list[list[Message]]) -> str:
    """Render exchanges into text for the summarization prompt."""
    parts: list[str] = []
    for exchange in exchanges:
        for msg in exchange:
            content = msg.content
            if isinstance(content, dict):
                content = json.dumps(content, default=str)
            elif not isinstance(content, str):
                content = str(content) if content else ""
            if not content:
                continue
            role = msg.role.upper()
            if msg.role == "tool":
                role = f"TOOL[{msg.name or '?'}]"
            parts.append(f"{role}: {content[:500]}")
    return "\n".join(parts)


async def summarize_old_exchanges(
    thread: list[Message],
    provider: LLMProvider,
    context_budget: int,
) -> list[Message]:
    """Replace old exchanges with LLM-generated summaries.

    Returns a new thread with old exchanges replaced by summary messages.
    """
    system_prefix, old_exchanges, recent_exchanges = _split_thread(thread)

    if not old_exchanges:
        return thread

    batch_size = max(3, len(old_exchanges) // 3)
    summaries: list[str] = []

    for i in range(0, len(old_exchanges), batch_size):
        batch = old_exchanges[i : i + batch_size]
        text = _exchanges_to_text(batch)
        if not text.strip():
            continue

        request = LLMRequest(
            model="",
            messages=[
                Message(role="system", content=_SUMMARIZE_SYSTEM),
                Message(role="user", content=text[:8000]),
            ],
            temperature=0.1,
            max_tokens=512,
        )

        try:
            response = await provider.complete(request)
            summary = (response.content or "").strip()
            if summary:
                summaries.append(summary)
        except Exception:
            logger.warning("compaction_summarize_failed", batch=i, exc_info=True)
            summaries.append(f"[Earlier exchanges {i+1}-{i+len(batch)} — summary unavailable]")

    summary_msgs = [
        Message(
            role="system",
            content=f"[Summary of earlier conversation]\n{s}",
        )
        for s in summaries
    ]

    recent_msgs = [msg for exchange in recent_exchanges for msg in exchange]

    result = system_prefix + summary_msgs + recent_msgs
    logger.info(
        "compaction_summarized",
        old_exchanges=len(old_exchanges),
        summaries=len(summaries),
        thread_before=len(thread),
        thread_after=len(result),
    )
    return result


async def compact_thread(
    thread: list[Message],
    provider: LLMProvider,
    context_budget: int,
) -> list[Message]:
    """Aggressively compact the thread into a single session briefing.

    Keeps only the system prefix, a compact summary, and recent exchanges.
    """
    system_prefix, old_exchanges, recent_exchanges = _split_thread(thread)

    all_old = old_exchanges
    if not all_old:
        return thread

    text = _exchanges_to_text(all_old)
    if not text.strip():
        return thread

    request = LLMRequest(
        model="",
        messages=[
            Message(role="system", content=_COMPACT_SYSTEM),
            Message(role="user", content=text[:12000]),
        ],
        temperature=0.1,
        max_tokens=768,
    )

    try:
        response = await provider.complete(request)
        briefing = (response.content or "").strip()
    except Exception:
        logger.warning("compaction_compact_failed", exc_info=True)
        briefing = "[Session history compacted — summary unavailable]"

    briefing_msg = Message(
        role="system",
        content=f"[Session briefing — earlier conversation compacted]\n{briefing}",
    )

    recent_msgs = [msg for exchange in recent_exchanges for msg in exchange]

    result = system_prefix + [briefing_msg] + recent_msgs
    logger.info(
        "compaction_compacted",
        old_exchanges=len(all_old),
        thread_before=len(thread),
        thread_after=len(result),
    )
    return result
