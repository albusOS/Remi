"""Remote agent executor — HTTP client implementing the AgentExecutor protocol.

Used when the task supervisor needs to run an agent on a different
process (worker fleet, remote container). The remote process must
expose the standard ``POST /api/v1/agents/{name}/ask`` endpoint.

This module is the ``worker`` placement adapter: the supervisor calls
``ask()`` here, which POSTs to a remote ``AgentRuntime`` over HTTP.
"""

from __future__ import annotations

from typing import Any

import structlog

from remi.agent.tasks.supervisor import AgentExecutor

logger = structlog.get_logger(__name__)


class RemoteAgentExecutor:
    """Execute agents via HTTP against a remote REMI API.

    Implements the ``AgentExecutor`` protocol so it can be injected into
    ``TaskSupervisor`` without changing any supervisor logic. The
    remote API endpoint streams NDJSON; this client consumes the stream
    and returns the final answer + run_id.
    """

    def __init__(self, base_url: str, timeout: float = 300.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def ask(
        self,
        agent_name: str,
        question: str,
        *,
        mode: str = "agent",
    ) -> tuple[str | None, str]:
        """POST to the remote agent endpoint and collect the result.

        Consumes the NDJSON streaming response, accumulates ``delta``
        events into the final answer, and extracts the ``run_id`` from
        the ``done`` event.
        """
        import json

        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError(
                "httpx is required for remote agent execution. Install it with: uv add httpx"
            ) from exc

        url = f"{self._base_url}/api/v1/agents/{agent_name}/ask"
        payload: dict[str, Any] = {"question": question, "mode": mode}

        log = logger.bind(agent=agent_name, url=url, mode=mode)
        log.info("remote_ask_start", question_length=len(question))

        answer_parts: list[str] = []
        run_id = ""

        async with (
            httpx.AsyncClient(timeout=self._timeout) as client,
            client.stream("POST", url, json=payload) as resp,
        ):
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                event_type = event.get("type", "")
                if event_type == "delta":
                    answer_parts.append(event.get("content", ""))
                elif event_type == "done":
                    run_id = event.get("run_id", "")
                elif event_type == "error":
                    error_msg = event.get("error", "Remote agent execution failed")
                    log.error("remote_ask_error", error=error_msg)
                    raise RuntimeError(error_msg)

        answer = "".join(answer_parts) or None
        log.info(
            "remote_ask_done",
            run_id=run_id,
            answer_length=len(answer) if answer else 0,
        )
        return (answer, run_id)


# Type assertion: RemoteAgentExecutor satisfies AgentExecutor
_: type[AgentExecutor] = RemoteAgentExecutor  # type: ignore[assignment]
