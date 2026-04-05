"""WebSocket connection manager — broadcast events to connected clients."""

from __future__ import annotations

import json
from typing import Any

import structlog
from fastapi import WebSocket

from remi.agent.observe import Event

logger = structlog.get_logger("remi.ws.manager")


class ConnectionManager:
    """Track active WebSocket connections and broadcast messages."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard(ws)

    @property
    def active_count(self) -> int:
        return len(self._connections)

    async def broadcast(self, event_type: str, data: dict[str, Any]) -> None:
        """Send a JSON event to all connected clients.

        Dead connections are silently removed.
        """
        if not self._connections:
            return

        payload = json.dumps({"type": event_type, "data": data}, default=str)
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                logger.warning(
                    Event.NOTIFICATION_SEND_FAILED,
                    exc_info=True,
                )
                dead.append(ws)
        for ws in dead:
            self._connections.discard(ws)


manager = ConnectionManager()
