"""Memory tools — in-process session state.

Provides: memory_store, memory_recall.
"""

from __future__ import annotations

from typing import Any

from remi.agent.graph.stores import MemoryStore
from remi.agent.types import ToolArg, ToolDefinition, ToolProvider, ToolRegistry


class MemoryToolProvider(ToolProvider):
    def __init__(self, memory_store: MemoryStore) -> None:
        self._memory_store = memory_store

    def register(self, registry: ToolRegistry) -> None:
        memory_store = self._memory_store

        async def mem_store(args: dict[str, Any]) -> Any:
            ns = args.get("namespace", "default")
            await memory_store.store(ns, args["key"], args["value"])
            return {"stored": True, "key": args["key"]}

        registry.register(
            "memory_store",
            mem_store,
            ToolDefinition(
                name="memory_store",
                description="Store a value in persistent memory for later recall.",
                args=[
                    ToolArg(name="key", description="Memory key", required=True),
                    ToolArg(name="value", description="Value to remember", required=True),
                    ToolArg(name="namespace", description="Optional namespace"),
                ],
            ),
        )

        async def mem_recall(args: dict[str, Any]) -> Any:
            ns = args.get("namespace", "default")
            if key := args.get("key"):
                value = await memory_store.recall(ns, key)
                return {"key": key, "value": value}
            if query := args.get("query"):
                entries = await memory_store.search(ns, query)
                return [{"key": e.key, "value": e.value} for e in entries]
            keys = await memory_store.list_keys(ns)
            return {"keys": keys}

        registry.register(
            "memory_recall",
            mem_recall,
            ToolDefinition(
                name="memory_recall",
                description="Recall a value from persistent memory by key, or search by query.",
                args=[
                    ToolArg(name="key", description="Exact key to recall"),
                    ToolArg(name="query", description="Search query"),
                    ToolArg(name="namespace", description="Optional namespace"),
                ],
            ),
        )
