"""Agent session management — multi-turn chat state persistence.

Owns session lifecycle (create, get, list, delete, append_message)
and nothing else. No LLM invocation, no YAML loading, no sandbox
management. The API layer and runtime both depend on this.
"""

from __future__ import annotations

import structlog

from remi.agent.types import ChatSession, ChatSessionStore, Message

logger = structlog.get_logger("remi.agent.sessions")


class AgentSessions:
    """Session CRUD — thin wrapper over the ChatSessionStore."""

    def __init__(self, store: ChatSessionStore) -> None:
        self._store = store

    async def create(
        self,
        agent: str,
        *,
        provider: str | None = None,
        model: str | None = None,
    ) -> ChatSession:
        return await self._store.create(agent, provider=provider, model=model)

    async def get(self, session_id: str) -> ChatSession | None:
        return await self._store.get(session_id)

    async def list(self) -> list[ChatSession]:
        return await self._store.list_sessions()

    async def delete(self, session_id: str) -> bool:
        return await self._store.delete(session_id)

    async def append_message(self, session_id: str, message: Message) -> None:
        await self._store.append_message(session_id, message)
