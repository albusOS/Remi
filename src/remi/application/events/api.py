"""Event feed — cursor-based HTTP polling endpoint.

Frontends and programmatic consumers poll ``GET /api/v1/feed`` with a
cursor to retrieve events since their last read.  Supports glob-based
topic filtering (e.g. ``types=ingestion.*,agent.completed``).

The endpoint is channel-agnostic — it serves whatever the ``EventBus``
carries.  Today that's ``domain.*`` events; ``agent.*`` and ``ui.*``
will follow when multi-agent orchestration is wired.
"""

from __future__ import annotations

import fnmatch
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from remi.agent.events.buffer import BufferedEvent
from remi.application.dependencies import Ctr

router = APIRouter(prefix="/feed", tags=["feed"])


class EventItem(BaseModel):
    seq: int
    topic: str
    payload: dict[str, Any]
    event_id: str
    timestamp: str
    source: str


class FeedResponse(BaseModel):
    events: list[EventItem]
    cursor: int
    has_more: bool


def _matches_types(topic: str, type_patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(topic, p) for p in type_patterns)


@router.get("", response_model=FeedResponse)
async def poll_feed(
    c: Ctr,
    after: int = Query(default=0, ge=0, description="Cursor — return events with seq > after"),
    types: str | None = Query(default=None, description="Comma-separated topic globs (e.g. ingestion.*,assertion.*)"),
    limit: int = Query(default=100, ge=1, le=500),
) -> FeedResponse:
    """Poll for events since the given cursor.

    Returns events ordered by sequence number.  The ``cursor`` in the
    response is the seq of the last returned event (or the input
    ``after`` if nothing matched).  Pass it back as ``after`` on the
    next request.
    """
    buf = c.event_buffer
    raw: list[BufferedEvent] = await buf.read_after(after, limit=limit + 50)

    type_patterns = [p.strip() for p in types.split(",") if p.strip()] if types else []

    items: list[EventItem] = []
    for entry in raw:
        if type_patterns and not _matches_types(entry.event.topic, type_patterns):
            continue
        items.append(
            EventItem(
                seq=entry.seq,
                topic=entry.event.topic,
                payload=entry.event.payload,
                event_id=entry.event.event_id,
                timestamp=entry.event.timestamp.isoformat(),
                source=entry.event.source,
            )
        )
        if len(items) >= limit:
            break

    cursor = items[-1].seq if items else after
    has_more = len(raw) > len(items)

    return FeedResponse(events=items, cursor=cursor, has_more=has_more)
