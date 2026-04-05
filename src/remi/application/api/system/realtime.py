"""WebSocket routes — lifecycle event broadcast.

The ``/ws/events`` endpoint pushes server-side events (ingestion complete,
signals updated, etc.) to connected frontends. A server-side heartbeat
keeps the connection alive through proxies.

Chat is handled by the REST streaming endpoint
``POST /api/v1/agents/{name}/ask`` via NDJSON — no WebSocket needed.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from remi.agent.observe import Event
from remi.application.realtime import connection_manager as manager

router = APIRouter(tags=["ws"])
logger = structlog.get_logger("remi.ws")

HEARTBEAT_INTERVAL_S = 25
PONG_TIMEOUT_S = 10

_PING_MSG = json.dumps({"type": "ping"})


class _Heartbeat:
    """Server-side heartbeat using app-level ping/pong JSON messages."""

    def __init__(self) -> None:
        self.last_pong: float = time.monotonic()

    def record_pong(self) -> None:
        self.last_pong = time.monotonic()

    async def run(self, ws: WebSocket, label: str) -> None:
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL_S)
                try:
                    await ws.send_text(_PING_MSG)
                except Exception:
                    logger.warning(Event.WS_PING_FAILED, endpoint=label, exc_info=True)
                    return

                await asyncio.sleep(PONG_TIMEOUT_S)
                if time.monotonic() - self.last_pong > HEARTBEAT_INTERVAL_S + PONG_TIMEOUT_S:
                    logger.warning("ws_pong_timeout", endpoint=label)
                    with contextlib.suppress(Exception):
                        await ws.close(code=4001, reason="pong timeout")
                    return
        except asyncio.CancelledError:
            pass


def _is_pong(raw: str) -> bool:
    return '"pong"' in raw and raw.strip().startswith("{")


@router.websocket("/ws/events")
async def events_ws(ws: WebSocket) -> None:
    client = ws.client.host if ws.client else "unknown"
    logger.info(Event.WS_EVENTS_CONNECT, client=client)
    await manager.connect(ws)
    hb = _Heartbeat()
    heartbeat_task = asyncio.create_task(hb.run(ws, "events"))
    try:
        while True:
            raw = await ws.receive_text()
            if _is_pong(raw):
                hb.record_pong()
    except WebSocketDisconnect:
        logger.info(Event.WS_EVENTS_DISCONNECT, client=client)
    finally:
        heartbeat_task.cancel()
        manager.disconnect(ws)
