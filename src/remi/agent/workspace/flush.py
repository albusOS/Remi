"""Flush-before-truncate — save dropped conversation context to workspace.

When ``trim_thread`` is about to drop old exchanges, this module first
summarizes them into ``CONTEXT.md`` in the sandbox workspace.  The agent
can read this file on subsequent turns to recover key information from
earlier in the conversation.

This is the "flush to disk before evicting from RAM" pattern:
conversation thread = RAM, workspace files = disk.
"""

from __future__ import annotations

import structlog

from remi.agent.llm.types import Message
from remi.agent.sandbox.types import Sandbox

_log = structlog.get_logger(__name__)

_CONTEXT_FILE = "CONTEXT.md"
_MAX_CONTEXT_CHARS = 12_000


def _extract_droppable_exchanges(
    thread: list[Message],
    max_turns: int,
) -> list[list[Message]]:
    """Return the exchanges that trim_thread *would* drop, without modifying the thread."""
    if max_turns <= 0:
        return []

    conversation: list[Message] = []
    for msg in thread:
        if not conversation and msg.role == "system":
            continue
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

    if len(exchanges) <= max_turns:
        return []

    return exchanges[: len(exchanges) - max_turns]


def _summarize_exchanges(exchanges: list[list[Message]]) -> str:
    """Build a compact Markdown summary of dropped exchanges."""
    parts: list[str] = []
    for i, exchange in enumerate(exchanges, 1):
        user_text = ""
        assistant_text = ""
        tool_names: list[str] = []
        for msg in exchange:
            if msg.role == "user" and msg.content:
                user_text = str(msg.content)[:300]
            elif msg.role == "assistant" and msg.content:
                assistant_text = str(msg.content)[:500]
            elif msg.role == "tool" and msg.name:
                tool_names.append(msg.name)

        entry = f"**Exchange {i}**"
        if user_text:
            entry += f"\n- User: {user_text}"
        if tool_names:
            entry += f"\n- Tools used: {', '.join(dict.fromkeys(tool_names))}"
        if assistant_text:
            entry += f"\n- Response: {assistant_text}"
        parts.append(entry)

    return "\n\n".join(parts)


async def flush_before_trim(
    thread: list[Message],
    max_turns: int,
    sandbox: Sandbox,
    session_id: str,
) -> None:
    """Summarize exchanges that will be dropped and append to CONTEXT.md.

    Called *before* ``trim_thread`` so the agent's workspace retains a
    record of the conversation history that's about to leave the context
    window.
    """
    droppable = _extract_droppable_exchanges(thread, max_turns)
    if not droppable:
        return

    summary = _summarize_exchanges(droppable)
    if not summary.strip():
        return

    session = await sandbox.get_session(session_id)
    if session is None:
        _log.warning("flush_skip_no_session", session_id=session_id)
        return

    existing = await sandbox.read_file(session_id, _CONTEXT_FILE)
    header = "# Conversation Context\n\nAccumulated context from earlier conversation turns.\n\n"

    if existing and existing.strip():
        new_content = existing.rstrip() + "\n\n---\n\n" + summary
    else:
        new_content = header + summary

    if len(new_content) > _MAX_CONTEXT_CHARS:
        overflow = len(new_content) - _MAX_CONTEXT_CHARS
        new_content = header + new_content[len(header) + overflow:]

    await sandbox.write_file(session_id, _CONTEXT_FILE, new_content)

    _log.info(
        "context_flushed",
        session_id=session_id,
        exchanges_flushed=len(droppable),
        context_chars=len(new_content),
    )
