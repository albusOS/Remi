"""Chat agent runner — multi-turn conversation over WebSocket.

Thin transport adapter: delegates agent execution to ChatAgentService.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import WebSocket

from remi.agent.runner import ChatAgentService
from remi.api.realtime.jsonrpc import (
    Dispatcher,
    JsonRpcNotification,
    JsonRpcRequest,
)
from remi.models.chat import ChatSessionStore

logger = structlog.get_logger("remi.chat_runner")


async def _resolve_manager_scope(
    property_store: Any,
    manager_id: str | None,
) -> dict[str, Any]:
    """Build extras dict with manager scope info when a manager is selected."""
    if not manager_id or property_store is None:
        return {}
    try:
        mgr = await property_store.get_manager(manager_id)
        if mgr is None:
            return {}
        portfolios = await property_store.list_portfolios(manager_id=manager_id)
        property_names: list[str] = []
        total_units = 0
        for p in portfolios:
            props = await property_store.list_properties(portfolio_id=p.id)
            for prop in props:
                property_names.append(prop.name)
                units = await property_store.list_units(property_id=prop.id)
                total_units += len(units)
        return {
            "manager_id": manager_id,
            "manager_name": mgr.name,
            "manager_property_count": len(property_names),
            "manager_property_names": property_names,
            "manager_unit_count": total_units,
        }
    except Exception:
        logger.debug("manager_scope_resolve_failed", manager_id=manager_id, exc_info=True)
        return {"manager_id": manager_id}


async def send_notification(ws: WebSocket, method: str, params: dict[str, Any]) -> None:
    notif = JsonRpcNotification(method=method, params=params)
    await ws.send_text(notif.to_json())


def build_chat_dispatcher(
    ws: WebSocket,
    chat_session_store: ChatSessionStore,
    chat_agent: ChatAgentService,
    *,
    property_store: Any = None,
) -> Dispatcher:
    from remi.models.chat import Message

    dp = Dispatcher()

    @dp.method("chat.create")
    async def chat_create(req: JsonRpcRequest) -> dict[str, Any]:
        agent = req.params.get("agent", "director")
        provider = req.params.get("provider")
        model = req.params.get("model")
        session = await chat_session_store.create(
            agent,
            provider=provider,
            model=model,
        )
        return {
            "session_id": session.id,
            "agent": session.agent,
            "provider": session.provider,
            "model": session.model,
        }

    @dp.method("chat.send")
    async def chat_send(req: JsonRpcRequest) -> dict[str, Any]:
        session_id = req.params.get("session_id")
        message_text = req.params.get("message", "")
        mode = req.params.get("mode", "agent")
        if mode not in ("ask", "agent"):
            mode = "agent"

        req_provider = req.params.get("provider")
        req_model = req.params.get("model")
        manager_id = req.params.get("manager_id")

        if not session_id:
            raise ValueError("session_id is required")

        log = logger.bind(session_id=session_id, mode=mode, manager_id=manager_id)
        log.info(
            "chat_send",
            message_length=len(message_text),
            provider=req_provider,
            model=req_model,
        )

        session = await chat_session_store.get(session_id)
        if session is None:
            raise ValueError(f"Session '{session_id}' not found")

        provider = req_provider or session.provider
        model = req_model or session.model

        manager_scope = await _resolve_manager_scope(property_store, manager_id)

        user_msg = Message(role="user", content=message_text)
        await chat_session_store.append_message(session_id, user_msg)

        session = await chat_session_store.get(session_id)
        assert session is not None

        async def on_event(event_type: str, data: dict[str, Any]) -> None:
            await send_notification(
                ws,
                f"chat.{event_type}",
                {
                    "session_id": session_id,
                    **data,
                },
            )

        try:
            answer = await chat_agent.run_chat_agent(
                session.agent,
                session.thread,
                on_event,
                mode=mode,
                sandbox_session_id=f"chat-{session_id}",
                provider=provider,
                model=model,
                extra=manager_scope,
            )
        except Exception as exc:
            log.error("chat_send_error", error=str(exc), error_type=type(exc).__name__)
            await send_notification(
                ws,
                "chat.error",
                {
                    "session_id": session_id,
                    "message": str(exc),
                },
            )
            raise

        assistant_msg = Message(role="assistant", content=answer)
        await chat_session_store.append_message(session_id, assistant_msg)

        return {"status": "ok", "session_id": session_id}

    @dp.method("chat.history")
    async def chat_history(req: JsonRpcRequest) -> dict[str, Any]:
        session_id = req.params.get("session_id")
        if not session_id:
            raise ValueError("session_id is required")
        session = await chat_session_store.get(session_id)
        if session is None:
            raise ValueError(f"Session '{session_id}' not found")
        return {
            "session_id": session.id,
            "agent": session.agent,
            "messages": [
                {"role": m.role, "content": m.content, "name": m.name}
                for m in session.thread
                if m.role in ("user", "assistant")
            ],
        }

    @dp.method("chat.list")
    async def chat_list(req: JsonRpcRequest) -> dict[str, Any]:
        sessions = await chat_session_store.list_sessions()
        return {
            "sessions": [
                {
                    "id": s.id,
                    "agent": s.agent,
                    "message_count": len([m for m in s.thread if m.role in ("user", "assistant")]),
                    "created_at": s.created_at.isoformat(),
                    "updated_at": s.updated_at.isoformat(),
                }
                for s in sessions
            ],
        }

    return dp
