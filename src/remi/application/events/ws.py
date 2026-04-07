"""Event feed — WebSocket push endpoint.

``WS /api/v1/feed/ws`` pushes events to connected clients in real time.
Each connection subscribes to the ``EventBus`` for the lifetime of the
socket; events are serialized as JSON and sent immediately.

Clients can filter by topic via the ``types`` query parameter
(comma-separated globs, e.g. ``?types=ingestion.*,agent.*``).
The endpoint is channel-agnostic — it delivers whatever the bus carries.

No custom ping/pong — uses the WebSocket protocol-level ping frames
that FastAPI/Starlette send automatically.  Connection health is
implicit: if the socket is open, you're live.

This handler gets the ``EventBus`` from the DI container via
``request.app.state`` — no singletons, no module-level globals.
"""

from __future__ import annotations

import asyncio
import fnmatch
import json

import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from remi.agent.events import DomainEvent, EventBus

router = APIRouter(tags=["feed"])
logger = structlog.get_logger("remi.events.ws")


def _matches(topic: str, patterns: list[str]) -> bool:
    if not patterns:
        return True
    return any(fnmatch.fnmatch(topic, p) for p in patterns)


def _serialize(event: DomainEvent) -> str:
    return json.dumps(
        {
            "topic": event.topic,
            "payload": event.payload,
            "event_id": event.event_id,
            "timestamp": event.timestamp.isoformat(),
            "source": event.source,
        },
        default=str,
    )


@router.websocket("/feed/ws")
async def feed_ws(
    ws: WebSocket,
    types: str | None = Query(default=None),
) -> None:
    """Push events to a WebSocket client.

    The bus subscription lives for the lifetime of the connection.
    Events are filtered server-side by ``types`` globs before sending.
    """
    container = ws.app.state.container
    bus: EventBus = container.event_bus
    type_patterns = [p.strip() for p in types.split(",") if p.strip()] if types else []

    await ws.accept()
    client = ws.client.host if ws.client else "unknown"
    logger.info("feed_ws_connect", client=client, types=type_patterns or "*")

    send_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=256)

    async def _on_event(event: DomainEvent) -> None:
        if not _matches(event.topic, type_patterns):
            return
        try:
            send_queue.put_nowait(_serialize(event))
        except asyncio.QueueFull:
            logger.warning("feed_ws_queue_full", client=client)

    unsub = bus.subscribe("*", _on_event)

    async def _sender() -> None:
        try:
            while True:
                msg = await send_queue.get()
                await ws.send_text(msg)
        except Exception:
            pass

    sender_task = asyncio.create_task(_sender())
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        unsub()
        sender_task.cancel()
        logger.info("feed_ws_disconnect", client=client)
