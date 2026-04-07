"""HTTP middleware — request-ID propagation and timing.

Pure ASGI middleware (no BaseHTTPMiddleware). Generates or propagates a
``request_id``, binds it to structlog context vars, echoes it in the
``X-Request-ID`` response header, and logs method/path/status/duration
for every HTTP request.
"""

from __future__ import annotations

import time
import uuid

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_REQUEST_ID_HEADER = "x-request-id"
_logger = structlog.get_logger("remi.http")


class RequestIDMiddleware:
    """Lightweight ASGI middleware — no BaseHTTPMiddleware overhead."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        request_id = headers.get(b"x-request-id", b"").decode() or uuid.uuid4().hex[:16]

        structlog.contextvars.bind_contextvars(request_id=request_id)
        t0 = time.monotonic()
        status_code = 0

        async def send_with_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 0)
                raw_headers: list[tuple[bytes, bytes]] = list(message.get("headers", []))
                raw_headers.append((b"x-request-id", request_id.encode()))
                message = {**message, "headers": raw_headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            duration_ms = round((time.monotonic() - t0) * 1000)
            path = scope.get("path", "")
            if not path.startswith("/ws/"):
                _logger.info(
                    "http_request",
                    method=scope.get("method", ""),
                    path=path,
                    status=status_code,
                    duration_ms=duration_ms,
                )
            structlog.contextvars.unbind_contextvars("request_id")
