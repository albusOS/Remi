"""Episode extraction — distill completed agent runs into persistent memories.

After an agent run completes, the extractor scans the conversation thread
and uses a cheap LLM call to produce structured observations.  Each
observation is classified into a ``MemoryNamespace``, assigned an
importance level, tagged with relevant entity IDs, and written to the
``MemoryStore``.

This replaces the naive "dump last assistant message" auto-save with a
deliberate consolidation step.  The extraction is fire-and-forget — it
should not block the response to the user.
"""

from __future__ import annotations

import json

import structlog

from remi.agent.llm.types import LLMProvider, Message
from remi.agent.memory.store import MemoryStore
from remi.agent.memory.types import IMPORTANCE_TTL, Importance, MemoryNamespace

logger = structlog.get_logger(__name__)

_EXTRACTION_SYSTEM = """\
You are a memory consolidation engine. Given a completed agent conversation, \
extract observations worth remembering for future sessions.

Output a JSON array. Each element has:
- "namespace": one of "episodic", "feedback", "reference", "plan"
- "key": short identifier (slug-style, e.g. "oak-st-vacancy-finding")
- "value": the observation — be specific, include conclusions and numbers
- "importance": 1 (routine), 2 (notable), or 3 (critical)
- "entity_ids": list of entity IDs mentioned (property IDs, manager IDs, etc.)
- "tags": list of topic tags for retrieval

Rules:
- Extract 1-5 observations. Prefer fewer high-quality entries over many vague ones.
- "feedback" = user corrections, mistakes the agent should avoid repeating.
- "reference" = stable facts learned (e.g. "manager X handles properties Y and Z").
- "episodic" = session-specific findings (e.g. "analyzed delinquency for Q1 2025").
- "plan" = only if there's an unfinished plan the agent should resume.
- Skip observations that are purely conversational or trivially obvious.
- importance 3 = the user explicitly corrected something, or a critical finding.
- importance 2 = a useful finding the agent should recall in related queries.
- importance 1 = routine session record.

Return ONLY the JSON array, no markdown fences or explanation."""

_MAX_THREAD_CHARS = 12_000
_CHARS_PER_TOKEN = 4


def _summarize_thread(thread: list[Message]) -> str:
    """Render the thread into a compact text representation for extraction."""
    parts: list[str] = []
    for msg in thread:
        if msg.role == "system":
            continue
        content = msg.content
        if isinstance(content, dict):
            content = json.dumps(content, default=str)
        elif not isinstance(content, str):
            content = str(content) if content else ""
        if not content:
            continue

        prefix = msg.role.upper()
        if msg.role == "tool":
            prefix = f"TOOL[{msg.name or '?'}]"

        parts.append(f"{prefix}: {content[:600]}")

    text = "\n".join(parts)
    if len(text) > _MAX_THREAD_CHARS:
        half = _MAX_THREAD_CHARS // 2
        text = text[:half] + "\n\n[...middle of conversation truncated...]\n\n" + text[-half:]
    return text


async def extract_episode(
    thread: list[Message],
    store: MemoryStore,
    provider: LLMProvider,
    *,
    model: str,
    run_id: str = "",
    agent_name: str = "",
) -> int:
    """Extract observations from a completed run and persist them.

    Returns the number of observations written.  Logs and returns 0
    on any failure — extraction must never break the agent response path.
    """
    if len(thread) < 4:
        return 0

    conversation = _summarize_thread(thread)
    if len(conversation) < 100:
        return 0

    messages = [
        Message(role="system", content=_EXTRACTION_SYSTEM),
        Message(
            role="user",
            content=f"Extract memories from this agent session:\n\n{conversation}",
        ),
    ]

    try:
        response = await provider.complete(
            model=model,
            messages=messages,
            temperature=0.2,
            max_tokens=2048,
        )
    except Exception:
        logger.warning("episode_extraction_llm_failed", run_id=run_id, exc_info=True)
        return 0

    raw = (response.content or "").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    try:
        observations = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning(
            "episode_extraction_parse_failed",
            run_id=run_id,
            raw_length=len(raw),
        )
        return 0

    if not isinstance(observations, list):
        return 0

    written = 0
    for obs in observations:
        if not isinstance(obs, dict):
            continue
        namespace = obs.get("namespace", MemoryNamespace.EPISODIC)
        key = obs.get("key", "")
        value = obs.get("value", "")
        if not key or not value:
            continue

        importance = min(int(obs.get("importance", 1)), Importance.CRITICAL)
        entity_ids = obs.get("entity_ids") or []
        tags = obs.get("tags") or []

        ttl = IMPORTANCE_TTL.get(Importance(importance))

        try:
            await store.write(
                namespace,
                key,
                value,
                importance=importance,
                entity_ids=entity_ids if isinstance(entity_ids, list) else [],
                tags=tags if isinstance(tags, list) else [],
                source=f"extraction:{agent_name}" if agent_name else "extraction",
                ttl=ttl,
            )
            written += 1
        except Exception:
            logger.warning(
                "episode_extraction_write_failed",
                key=key,
                run_id=run_id,
                exc_info=True,
            )

    logger.info(
        "episode_extraction_done",
        run_id=run_id,
        agent=agent_name,
        observations=written,
        total_attempted=len(observations),
    )
    return written
