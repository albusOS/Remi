"""Agent types — chat session management, tool registry, and memory ports.

Wire types (Message, ToolCallRequest, ToolDefinition, ToolArg) live in
``remi.agent.llm.types`` — this module re-exports them for backward compatibility
and adds the agent-specific session / registry contracts.
"""

from __future__ import annotations

import abc
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from remi.agent.llm.types import Message, ToolArg, ToolCallRequest, ToolDefinition

__all__ = [
    "Message",
    "ToolCallRequest",
    "ToolArg",
    "ToolDefinition",
    "ToolResult",
    "ToolBinding",
    "ChatSession",
    "AgentEvent",
    "ChatEvent",
    "ChatSessionStore",
    "ToolFn",
    "ToolRegistry",
    "ToolCatalog",
    "ToolProvider",
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
    sandbox_session_id: str | None = None
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
# Tool result — standard output contract for all tool implementations
# ---------------------------------------------------------------------------


class ToolResult(BaseModel):
    """Standard output envelope for tool executions.

    Every tool SHOULD return a ``ToolResult`` so the runtime and downstream
    consumers can distinguish success from failure without inspecting
    ad-hoc dict shapes.  Existing tools that return raw dicts continue to
    work — the runtime serialises whatever it gets — but new tools should
    adopt this contract.

    Fields
    ------
    ok:
        ``True`` when the tool completed successfully.
    data:
        The primary payload (search hits, action item, stats, etc.).
        ``None`` on error.
    error:
        Human-readable error message.  ``None`` on success.
    metadata:
        Optional provenance, timing, or debug information.
    """

    ok: bool = True
    data: Any = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def success(cls, data: Any, **meta: Any) -> ToolResult:
        return cls(ok=True, data=data, metadata=meta)

    @classmethod
    def fail(cls, error: str, **meta: Any) -> ToolResult:
        return cls(ok=False, error=error, metadata=meta)


# ---------------------------------------------------------------------------
# Tool binding — a fully resolved capability owned by an agent run
# ---------------------------------------------------------------------------

ToolFn = Callable[[dict[str, Any]], Awaitable[Any]]


@dataclass(frozen=True)
class ToolBinding:
    """A fully resolved tool capability owned by an agent run.

    Unlike the old ``(list[ToolDefinition], execute_fn)`` tuple where one
    shared closure dispatched all tools by name, each ``ToolBinding`` is
    self-contained: its own definition (what the LLM sees), its own
    execution function (with agent-specific config already baked in),
    and provenance metadata.
    """

    definition: ToolDefinition
    execute: ToolFn
    source: str = ""


# ---------------------------------------------------------------------------
# Tool registry — capability type catalog
# ---------------------------------------------------------------------------


class ToolRegistry(abc.ABC):
    """Base registry contract — stores tool implementations by name.

    ``ToolProvider`` implementations call ``register()`` at startup.
    The workflow engine and legacy paths consume ``get()`` /
    ``list_definitions()``.

    Tools can be registered with a ``namespace`` to scope them to a
    specific workspace. Tools without a namespace are global (kernel
    tools like ``bash``, ``python``, ``memory_*``). Lookup methods
    accept an optional ``namespace`` — when provided, both namespaced
    and global tools are visible; when omitted, only global tools.
    """

    @abc.abstractmethod
    def register(
        self,
        name: str,
        fn: ToolFn,
        definition: ToolDefinition,
        *,
        namespace: str = "",
    ) -> None: ...

    @abc.abstractmethod
    def get(
        self,
        name: str,
        *,
        namespace: str = "",
    ) -> tuple[ToolFn, ToolDefinition] | None: ...

    @abc.abstractmethod
    def list_tools(self, *, namespace: str = "") -> list[ToolDefinition]: ...

    @abc.abstractmethod
    def list_definitions(
        self,
        names: list[str] | None = None,
        *,
        namespace: str = "",
    ) -> list[ToolDefinition]:
        """Return tool definitions, optionally filtered by name and namespace."""
        ...

    @abc.abstractmethod
    def has(self, name: str, *, namespace: str = "") -> bool: ...


class ToolCatalog(ToolRegistry):
    """Extended registry that produces agent-specific ``ToolBinding`` instances.

    ``ToolProviders`` register capability implementations here via the
    inherited ``register()`` method.  When an agent needs a tool, the
    catalog's ``resolve()`` method produces a ``ToolBinding`` configured
    for that specific agent context — description overrides, config
    merging, and context injection are all handled at resolution time,
    not at call time.
    """

    @abc.abstractmethod
    def resolve(
        self,
        name: str,
        *,
        namespace: str = "",
        agent_config: dict[str, Any] | None = None,
        agent_description: str | None = None,
        inject: dict[str, str] | None = None,
        context_values: dict[str, Any] | None = None,
    ) -> ToolBinding | None:
        """Produce an agent-specific binding for a registered tool.

        Parameters
        ----------
        name:
            Registered tool name.
        namespace:
            Workspace tool namespace. When set, looks up namespaced tools
            first, then falls back to global tools. When empty, only
            global tools are visible.
        agent_config:
            Per-agent config dict merged into arguments before the base
            ``ToolFn``.  Comes from ``ToolRef.config``.
        agent_description:
            If set, replaces the base ``ToolDefinition.description`` in
            the returned binding.  Comes from ``ToolRef.description``.
        inject:
            Maps argument names to context keys.  Any key present in
            *context_values* is auto-injected into arguments if not
            already provided by the caller.  Comes from ``ToolRef.inject``.
        context_values:
            Flat dict of runtime context values (e.g. ``sandbox_session_id``)
            available for injection.
        """
        ...

    @abc.abstractmethod
    def list_names(self, *, namespace: str = "") -> list[str]: ...


class ToolProvider(abc.ABC):
    """A self-contained unit that registers tools onto a ToolRegistry.

    Each provider owns its dependencies — it receives them at construction
    time and registers tools with their closures fully bound.  The container
    builds providers, then calls ``register`` on each one.

    Providers may pass a ``namespace`` to ``registry.register()`` to scope
    their tools to a specific workspace. Kernel providers (bash, python,
    memory) register globally (empty namespace). Domain providers
    (ServiceM8, Xero, Hike POS) register under their workspace namespace.
    """

    @abc.abstractmethod
    def register(self, registry: ToolRegistry, *, namespace: str = "") -> None: ...
