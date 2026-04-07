"""Memory tools — explicit read/write access to persistent agent memory.

Two tools:

- ``memory_read``  — the agent decides when to recall prior knowledge
- ``memory_write`` — the agent decides what is worth remembering

The old ``memory_store`` / ``memory_recall`` tools are replaced by
these semantically clearer operations with namespace and entity
awareness.
"""

from __future__ import annotations

from typing import Any

from remi.agent.memory import Importance, MemoryNamespace, MemoryStore
from remi.agent.types import ToolArg, ToolDefinition, ToolProvider, ToolRegistry

_NAMESPACE_HINT = (
    f"One of: {', '.join(ns.value for ns in MemoryNamespace)}. "
    "Defaults to 'episodic'."
)


class MemoryToolProvider(ToolProvider):
    def __init__(self, memory_store: MemoryStore) -> None:
        self._store = memory_store

    def register(self, registry: ToolRegistry) -> None:
        store = self._store

        async def memory_write(args: dict[str, Any]) -> Any:
            namespace = args.get("namespace", MemoryNamespace.EPISODIC)
            key = args.get("key", "")
            content = args.get("content", "")

            if not key or not content:
                return {"error": "Both 'key' and 'content' are required"}

            importance = min(int(args.get("importance", Importance.ROUTINE)), Importance.CRITICAL)

            entity_ids = args.get("entity_ids") or []
            if isinstance(entity_ids, str):
                entity_ids = [e.strip() for e in entity_ids.split(",") if e.strip()]

            tags = args.get("tags") or []
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]

            await store.write(
                namespace,
                key,
                content,
                importance=importance,
                entity_ids=entity_ids,
                tags=tags,
                source="agent",
            )
            return {
                "stored": True,
                "namespace": namespace,
                "key": key,
                "importance": importance,
                "entity_ids": entity_ids,
                "tags": tags,
            }

        registry.register(
            "memory_write",
            memory_write,
            ToolDefinition(
                name="memory_write",
                description=(
                    "Write something worth remembering to persistent memory. "
                    "Use this to record findings, corrections, plans, or reference "
                    "facts that should survive across sessions. Tag with entity_ids "
                    "so future queries about those entities surface this memory."
                ),
                args=[
                    ToolArg(
                        name="key",
                        description="Short identifier for this memory (e.g. 'oak-st-manager-correction')",
                        required=True,
                    ),
                    ToolArg(
                        name="content",
                        description="The information to remember — be specific and include conclusions",
                        required=True,
                    ),
                    ToolArg(name="namespace", description=_NAMESPACE_HINT),
                    ToolArg(
                        name="importance",
                        description=(
                            "1=routine (14d retention), 2=notable (90d), 3=critical (permanent). "
                            "Use 3 for user corrections. Defaults to 1."
                        ),
                    ),
                    ToolArg(
                        name="entity_ids",
                        description="Comma-separated entity IDs this memory relates to",
                    ),
                    ToolArg(
                        name="tags",
                        description="Comma-separated tags for retrieval filtering",
                    ),
                ],
            ),
        )

        async def memory_read(args: dict[str, Any]) -> Any:
            namespace = args.get("namespace", MemoryNamespace.EPISODIC)
            query = args.get("query", "")
            limit = int(args.get("limit", 10))

            entity_ids = args.get("entity_ids") or []
            if isinstance(entity_ids, str):
                entity_ids = [e.strip() for e in entity_ids.split(",") if e.strip()]

            tags = args.get("tags") or []
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]

            if not query and not entity_ids and not tags:
                keys = await store.list_keys(namespace)
                return {"namespace": namespace, "keys": keys, "count": len(keys)}

            entries = await store.read(
                namespace,
                query,
                entity_ids=entity_ids or None,
                tags=tags or None,
                limit=limit,
            )

            return {
                "namespace": namespace,
                "query": query,
                "count": len(entries),
                "entries": [
                    {
                        "key": e.key,
                        "content": e.value,
                        "importance": e.importance,
                        "entity_ids": e.entity_ids,
                        "tags": e.tags,
                        "created_at": e.created_at.isoformat() if e.created_at else None,
                    }
                    for e in entries
                ],
            }

        registry.register(
            "memory_read",
            memory_read,
            ToolDefinition(
                name="memory_read",
                description=(
                    "Read from persistent memory. Search by text query, filter by "
                    "entity IDs or tags, or list all keys in a namespace. Use this "
                    "to recall prior findings, corrections, or plans before starting "
                    "analysis."
                ),
                args=[
                    ToolArg(
                        name="query",
                        description="Text search query (e.g. 'delinquent properties' or 'manager corrections')",
                    ),
                    ToolArg(name="namespace", description=_NAMESPACE_HINT),
                    ToolArg(
                        name="entity_ids",
                        description="Comma-separated entity IDs to filter by",
                    ),
                    ToolArg(
                        name="tags",
                        description="Comma-separated tags to filter by",
                    ),
                    ToolArg(name="limit", description="Max entries to return (default 10)"),
                ],
            ),
        )
