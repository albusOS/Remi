"""Agent types — chat session management, tool registry, and memory ports.

Wire types (Message, ToolCallRequest, ToolDefinition, ToolArg) live in
``remi.llm.types`` — this module re-exports them for backward compatibility
and adds the agent-specific session / registry contracts.
"""

from __future__ import annotations

import abc
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from remi.llm.types import Message, ToolArg, ToolCallRequest, ToolDefinition

# Re-export so existing `from remi.agent.types import Message` still works
__all__ = [
    "Message",
    "ToolCallRequest",
    "ToolArg",
    "ToolDefinition",
    "ChatSession",
    "AgentEvent",
    "ChatEvent",
    "ChatSessionStore",
    "ToolFn",
    "ToolRegistry",
]


# ---------------------------------------------------------------------------
# Chat sessions
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ChatSession(BaseModel):
    """A persistent multi-turn conversation with a REMI agent."""

    id: str
    agent: str = "director"
    provider: str | None = None
    model: str | None = None
    thread: list[Message] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class AgentEvent(BaseModel, frozen=True):
    """Typed payload for agent runtime events (tool calls, deltas, etc.)."""

    event_type: str
    content: str | None = None
    tool_name: str | None = None
    tool_call_id: str | None = None
    tool_result: Any = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatEvent(BaseModel):
    """A streaming event emitted during agent execution."""

    event_type: str  # delta, tool_call, tool_result, done, error
    session_id: str
    data: dict[str, Any] = Field(default_factory=dict)


class ChatSessionStore(abc.ABC):
    @abc.abstractmethod
    async def create(
        self,
        agent: str,
        session_id: str | None = None,
        *,
        provider: str | None = None,
        model: str | None = None,
    ) -> ChatSession: ...

    @abc.abstractmethod
    async def get(self, session_id: str) -> ChatSession | None: ...

    @abc.abstractmethod
    async def append_message(self, session_id: str, message: Message) -> None: ...

    @abc.abstractmethod
    async def list_sessions(self) -> list[ChatSession]: ...

    @abc.abstractmethod
    async def delete(self, session_id: str) -> bool: ...


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------
ToolFn = Callable[[dict[str, Any]], Awaitable[Any]]


class ToolRegistry(abc.ABC):
    @abc.abstractmethod
    def register(self, name: str, fn: ToolFn, definition: ToolDefinition) -> None: ...

    @abc.abstractmethod
    def get(self, name: str) -> tuple[ToolFn, ToolDefinition] | None: ...

    @abc.abstractmethod
    def list_tools(self) -> list[ToolDefinition]: ...

    @abc.abstractmethod
    def list_definitions(self, names: list[str] | None = None) -> list[ToolDefinition]:
        """Return tool definitions, optionally filtered by name."""
        ...

    @abc.abstractmethod
    def has(self, name: str) -> bool: ...
