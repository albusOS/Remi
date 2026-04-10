"""In-memory tool catalog — capability type registry with per-agent resolution.

``InMemoryToolCatalog`` extends ``InMemoryToolRegistry`` with ``resolve()``,
which produces agent-specific ``ToolBinding`` instances.  Providers still
call ``register(name, fn, definition)``; the new path is consumed by
``resolve_agent_tools()`` in the tool executor.

Tools are stored in a two-level dict keyed by ``(namespace, name)``.
Namespace ``""`` (empty string) means global — kernel tools like bash,
python, memory that are available to all workspaces. When looking up a
tool with a non-empty namespace, the registry checks the namespace first
then falls back to global.
"""

from __future__ import annotations

from typing import Any

from remi.agent.types import (
    ToolBinding,
    ToolCatalog,
    ToolDefinition,
    ToolFn,
    ToolRegistry,
)

_GLOBAL = ""


class InMemoryToolRegistry(ToolRegistry):
    """Namespace-aware function-table registry."""

    def __init__(self) -> None:
        self._tools: dict[tuple[str, str], tuple[ToolFn, ToolDefinition]] = {}

    def register(
        self,
        name: str,
        fn: ToolFn,
        definition: ToolDefinition,
        *,
        namespace: str = _GLOBAL,
    ) -> None:
        self._tools[(namespace, name)] = (fn, definition)

    def _lookup(self, name: str, namespace: str) -> tuple[ToolFn, ToolDefinition] | None:
        """Namespace-first lookup with global fallback."""
        if namespace:
            entry = self._tools.get((namespace, name))
            if entry is not None:
                return entry
        return self._tools.get((_GLOBAL, name))

    def get(
        self,
        name: str,
        *,
        namespace: str = _GLOBAL,
    ) -> tuple[ToolFn, ToolDefinition] | None:
        return self._lookup(name, namespace)

    def _visible_tools(self, namespace: str) -> dict[str, ToolDefinition]:
        """Return {name: definition} for all tools visible in a namespace."""
        visible: dict[str, ToolDefinition] = {}
        for (ns, tool_name), (_, defn) in self._tools.items():
            if ns == _GLOBAL:
                visible.setdefault(tool_name, defn)
            elif ns == namespace:
                visible[tool_name] = defn
        return visible

    def list_tools(self, *, namespace: str = _GLOBAL) -> list[ToolDefinition]:
        return list(self._visible_tools(namespace).values())

    def list_definitions(
        self,
        names: list[str] | None = None,
        *,
        namespace: str = _GLOBAL,
    ) -> list[ToolDefinition]:
        visible = self._visible_tools(namespace)
        if names is not None:
            return [d for n, d in visible.items() if n in names]
        return list(visible.values())

    def has(self, name: str, *, namespace: str = _GLOBAL) -> bool:
        return self._lookup(name, namespace) is not None


class InMemoryToolCatalog(InMemoryToolRegistry, ToolCatalog):
    """Capability catalog that produces per-agent ``ToolBinding`` instances.

    Inherits the namespace-aware registry for provider registration and
    workflow-engine compatibility. Adds ``resolve()`` which applies
    agent-specific config, description overrides, and context injection
    at resolution time — so the returned ``ToolBinding.execute`` is a
    self-contained closure that needs no further merging at call time.
    """

    def resolve(
        self,
        name: str,
        *,
        namespace: str = _GLOBAL,
        agent_config: dict[str, Any] | None = None,
        agent_description: str | None = None,
        inject: dict[str, str] | None = None,
        context_values: dict[str, Any] | None = None,
    ) -> ToolBinding | None:
        entry = self._lookup(name, namespace)
        if entry is None:
            return None
        fn, base_definition = entry

        definition = base_definition
        if agent_description:
            definition = base_definition.model_copy(update={"description": agent_description})

        cfg = agent_config or {}
        inj = inject or {}
        ctx = context_values or {}

        async def bound_execute(args: dict[str, Any]) -> Any:
            merged = {**cfg, **args}
            for arg_name, ctx_key in inj.items():
                if arg_name not in merged:
                    val = ctx.get(ctx_key)
                    if val is not None:
                        merged[arg_name] = val
            if "caller_agent" in ctx:
                merged.setdefault("caller_agent", ctx["caller_agent"])
            return await fn(merged)

        return ToolBinding(
            definition=definition,
            execute=bound_execute,
            source=name,
        )

    def list_names(self, *, namespace: str = _GLOBAL) -> list[str]:
        return list(self._visible_tools(namespace).keys())
