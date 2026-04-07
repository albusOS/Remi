"""In-memory tool catalog — capability type registry with per-agent resolution.

``InMemoryToolCatalog`` extends ``InMemoryToolRegistry`` with ``resolve()``,
which produces agent-specific ``ToolBinding`` instances.  Providers still
call ``register(name, fn, definition)``; the new path is consumed by
``resolve_agent_tools()`` in the tool executor.
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


class InMemoryToolRegistry(ToolRegistry):
    """Flat function-table registry — backward-compat for workflow engine."""

    def __init__(self) -> None:
        self._tools: dict[str, tuple[ToolFn, ToolDefinition]] = {}

    def register(self, name: str, fn: ToolFn, definition: ToolDefinition) -> None:
        self._tools[name] = (fn, definition)

    def get(self, name: str) -> tuple[ToolFn, ToolDefinition] | None:
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDefinition]:
        return [defn for _, defn in self._tools.values()]

    def list_definitions(self, names: list[str] | None = None) -> list[ToolDefinition]:
        result: list[ToolDefinition] = []
        for tool_name, (_, defn) in self._tools.items():
            if names is not None and tool_name not in names:
                continue
            result.append(defn)
        return result

    def has(self, name: str) -> bool:
        return name in self._tools


class InMemoryToolCatalog(InMemoryToolRegistry, ToolCatalog):
    """Capability catalog that produces per-agent ``ToolBinding`` instances.

    Inherits the flat registry for provider registration and workflow-engine
    compatibility.  Adds ``resolve()`` which applies agent-specific config,
    description overrides, and context injection at resolution time — so the
    returned ``ToolBinding.execute`` is a self-contained closure that needs
    no further merging at call time.
    """

    def resolve(
        self,
        name: str,
        *,
        agent_config: dict[str, Any] | None = None,
        agent_description: str | None = None,
        inject: dict[str, str] | None = None,
        context_values: dict[str, Any] | None = None,
    ) -> ToolBinding | None:
        entry = self._tools.get(name)
        if entry is None:
            return None
        fn, base_definition = entry

        definition = base_definition
        if agent_description:
            definition = base_definition.model_copy(
                update={"description": agent_description}
            )

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

    def list_names(self) -> list[str]:
        return list(self._tools.keys())
