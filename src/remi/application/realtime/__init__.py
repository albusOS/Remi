"""Realtime communication — WebSocket event broadcasting.

The broadcast channel (``/ws/events``) pushes lifecycle events
(ingestion complete, signals updated, etc.) to connected frontends.

Chat is handled via the REST streaming endpoint
``POST /api/v1/agents/{name}/ask`` — no WebSocket needed.
"""

from remi.application.realtime.connection_manager import manager as connection_manager

__all__ = [
    "connection_manager",
]
