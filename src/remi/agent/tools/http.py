"""HTTP request tool — read-only access to the REMI API surface.

Constrained to GET requests against the configured internal REMI API base URL.
Mutations (POST, PATCH, DELETE) are blocked — agents perform writes through
dedicated workflow tools or the sandbox SDK, both of which have explicit,
auditable contracts.

The allowed host is derived from ``api_base_url`` at construction time so the
tool works correctly whether the API is on loopback, a Docker network hostname,
or an internal VPC address.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import structlog

from remi.agent.types import ToolArg, ToolDefinition, ToolProvider, ToolRegistry

logger = structlog.get_logger("remi.agent.tools.http")


class HttpToolProvider(ToolProvider):
    def __init__(
        self,
        *,
        api_base_url: str = "http://127.0.0.1:8000",
        api_path_examples: str = "",
    ) -> None:
        self._base = api_base_url.rstrip("/")
        self._api_path_examples = api_path_examples
        # Derive the allowed hostname from the configured base URL so this tool
        # works on any internal address (loopback, Docker network, VPC hostname).
        self._allowed_host = urlparse(self._base).hostname or "127.0.0.1"

    def register(self, registry: ToolRegistry) -> None:
        _base = self._base
        _allowed_host = self._allowed_host

        async def http_request(args: dict[str, Any]) -> Any:
            method = (args.get("method", "GET")).upper()
            path = args.get("path", "")
            timeout = min(int(args.get("timeout", 30)), 120)

            if method != "GET":
                return {
                    "error": (
                        "http_request is read-only (GET). "
                        "Use the remi SDK in Python for mutations "
                        "(remi.create_action, remi.create_note)."
                    ),
                }

            if not path:
                return {"error": "path is required"}

            if not path.startswith("/"):
                path = f"/{path}"

            url = f"{_base}{path}"

            parsed = urlparse(url)
            if parsed.hostname != _allowed_host:
                return {
                    "error": (
                        f"Requests to {parsed.hostname} are not allowed. "
                        f"Only the configured REMI API ({_allowed_host}) is permitted."
                    ),
                }

            import aiohttp

            try:
                async with aiohttp.ClientSession() as session:
                    kwargs: dict[str, Any] = {
                        "timeout": aiohttp.ClientTimeout(total=timeout),
                        "headers": {"Accept": "application/json"},
                    }

                    async with session.get(url, **kwargs) as resp:
                        status = resp.status
                        try:
                            response_body = await resp.json()
                        except Exception:
                            response_body = await resp.text()

                        return {
                            "status": status,
                            "body": response_body,
                            "url": url,
                            "method": method,
                        }

            except Exception as exc:
                logger.error(
                    "http_request_error",
                    url=url,
                    method=method,
                    error=str(exc),
                    exc_info=True,
                )
                return {"error": str(exc), "url": url, "method": method}

        base_desc = (
            "Read data from the REMI API (GET only). Use for endpoints "
            "not covered by other tools. For mutations, use the remi SDK "
            "in Python (remi.create_action, remi.create_note).\n\n"
            "Base URL is auto-configured. Pass only the path."
        )
        if self._api_path_examples:
            base_desc = f"{base_desc}\n\n{self._api_path_examples}"

        registry.register(
            "http_request",
            http_request,
            ToolDefinition(
                name="http_request",
                description=base_desc,
                args=[
                    ToolArg(
                        name="path",
                        description="API path (e.g. /api/v1/managers). Base URL is automatic.",
                        required=True,
                    ),
                    ToolArg(
                        name="timeout",
                        description="Timeout in seconds (default 30, max 120)",
                    ),
                ],
            ),
        )
