"""Agent chat streaming and session CRUD — HTTP plumbing over AgentRuntime.

Agent chat uses NDJSON streaming: ephemeral per-session telemetry
(``delta``, ``tool_call``, ``tool_result``, ``done``) flows directly
from the runtime callback through an ``asyncio.Queue`` into a
``StreamingResponse``.  This is a separate channel from the domain
``EventBus``, which carries world-state transitions only.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from remi.agent.runtime.deps import ScopeContext
from remi.shell.config.container import Container
from remi.types.errors import NotFoundError

logger = structlog.get_logger("remi.api.chat")


def _get_container(request: Request) -> Container:
    return request.app.state.container  # type: ignore[return-value]


_Ctr = Annotated[Container, Depends(_get_container)]

router = APIRouter(prefix="/agents", tags=["ai"])


# ---------------------------------------------------------------------------
# Streaming agent ask — NDJSON over StreamingResponse
# ---------------------------------------------------------------------------


class AskRequest(BaseModel):
    question: str
    session_id: str | None = None
    manager_id: str | None = None


@router.post("/{agent_name}/ask")
async def ask_agent(
    agent_name: str,
    body: AskRequest,
    c: _Ctr,
) -> StreamingResponse:
    """Stream an agent response as newline-delimited JSON events.

    Each line is a JSON object with ``event`` and ``data`` keys:
    ``delta``, ``tool_call``, ``tool_result``, ``phase``, ``done``.
    """
    scope: ScopeContext | None = None
    if body.manager_id:
        manager = await c.property_store.get_manager(body.manager_id)
        name = manager.name if manager else body.manager_id
        scope = ScopeContext(
            entity_id=body.manager_id,
            entity_type="PropertyManager",
            scope_message=(
                f"You are currently scoped to {name}'s portfolio "
                f"(manager_id: {body.manager_id!r}). "
                f"Unless the user explicitly asks about another manager, "
                f"pass manager_id={body.manager_id!r} to all query operations."
            ),
            tool_scope={"manager_id": body.manager_id},
        )

    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def _on_event(event_type: str, data: dict[str, Any]) -> None:
        line = json.dumps({"event": event_type, "data": data}, default=str)
        await queue.put(line)

    async def _run() -> None:
        try:
            await c.chat_agent.ask(
                agent_name,
                body.question,
                session_id=body.session_id,
                on_event=_on_event,
                scope=scope,
            )
        except Exception:
            logger.warning("ask_stream_failed", agent=agent_name, exc_info=True)
            await queue.put(
                json.dumps({"event": "error", "data": {"message": "agent execution failed"}})
            )
        finally:
            await queue.put(None)

    async def _stream() -> AsyncIterator[str]:
        task = asyncio.create_task(_run())
        try:
            while True:
                line = await queue.get()
                if line is None:
                    break
                yield line + "\n"
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(_stream(), media_type="application/x-ndjson")


# ---------------------------------------------------------------------------
# Session CRUD — REST surface over ChatSessionStore
# ---------------------------------------------------------------------------


class CreateSessionRequest(BaseModel):
    agent: str = "director"
    provider: str | None = None
    model: str | None = None


@router.post("/sessions")
async def create_session(
    body: CreateSessionRequest,
    c: _Ctr,
) -> dict[str, Any]:
    session = await c.chat_agent.sessions.create(
        body.agent,
        provider=body.provider,
        model=body.model,
    )
    return _session_dict(session)


@router.get("/sessions")
async def list_sessions(c: _Ctr) -> dict[str, Any]:
    all_sessions = await c.chat_agent.sessions.list()
    return {
        "count": len(all_sessions),
        "sessions": [_session_summary(s) for s in all_sessions],
    }


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    c: _Ctr,
) -> dict[str, Any]:
    session = await c.chat_agent.sessions.get(session_id)
    if session is None:
        raise NotFoundError("Session", session_id)
    return _session_dict(session)


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    c: _Ctr,
) -> dict[str, Any]:
    deleted = await c.chat_agent.sessions.delete(session_id)
    return {"deleted": deleted, "session_id": session_id}


def _session_dict(s: Any) -> dict[str, Any]:
    return {
        "session_id": s.id,
        "agent": s.agent,
        "provider": s.provider,
        "model": s.model,
        "sandbox_session_id": s.sandbox_session_id,
        "created_at": s.created_at.isoformat(),
        "updated_at": s.updated_at.isoformat(),
        "message_count": len(s.thread),
        "messages": [{"role": m.role, "content": m.content} for m in s.thread],
    }


def _session_summary(s: Any) -> dict[str, Any]:
    return {
        "session_id": s.id,
        "agent": s.agent,
        "created_at": s.created_at.isoformat(),
        "updated_at": s.updated_at.isoformat(),
        "message_count": len(s.thread),
    }
