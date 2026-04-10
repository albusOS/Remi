"""Memory recall service — relevance-ranked retrieval across namespaces.

Replaces the naive "list first 10 keys" pattern in AgentNode with a
proper ranked retrieval that:

- Searches across multiple namespaces simultaneously
- Ranks by importance and recency
- Deduplicates entries with overlapping keys
- Respects a token budget to avoid bloating context
- Renders results into a system message the agent can reason over

The recall service is injected into the runtime via ``RunDeps``.
"""

from __future__ import annotations

from remi.agent.memory.store import MemoryStore
from remi.agent.memory.types import MemoryEntry, MemoryNamespace, RecallService

_CHARS_PER_TOKEN = 4
_DEFAULT_TOKEN_BUDGET = 2000


class MemoryRecallService(RecallService):
    """Cross-namespace memory retrieval with relevance ranking."""

    def __init__(
        self,
        store: MemoryStore,
        *,
        token_budget: int = _DEFAULT_TOKEN_BUDGET,
    ) -> None:
        self._store = store
        self._token_budget = token_budget

    async def recall(
        self,
        question: str | None = None,
        *,
        namespaces: list[str] | None = None,
        entity_ids: list[str] | None = None,
        tags: list[str] | None = None,
        limit: int = 15,
    ) -> list[MemoryEntry]:
        """Retrieve relevant memories ranked by importance and recency.

        Searches all provided namespaces (defaults to all four) and
        merges results into a single ranked list.
        """
        if namespaces is None:
            namespaces = [ns.value for ns in MemoryNamespace]

        all_entries: list[MemoryEntry] = []
        seen_keys: set[str] = set()

        for ns in namespaces:
            entries = await self._store.read(
                ns,
                question or "",
                entity_ids=entity_ids,
                tags=tags,
                limit=limit,
            )
            for entry in entries:
                composite = f"{entry.namespace}:{entry.key}"
                if composite not in seen_keys:
                    seen_keys.add(composite)
                    all_entries.append(entry)

        all_entries.sort(
            key=lambda e: (
                e.importance,
                (e.created_at.timestamp() if e.created_at else 0.0),
            ),
            reverse=True,
        )

        return self._trim_to_budget(all_entries[:limit])

    def render(self, entries: list[MemoryEntry]) -> str | None:
        """Format recalled memories as a system message.

        Returns None if there are no entries to render.
        """
        if not entries:
            return None

        sections: dict[str, list[str]] = {}
        for entry in entries:
            label = _namespace_label(entry.namespace)
            line = f"- **{entry.key}**: {entry.value}"
            if entry.entity_ids:
                line += f" [entities: {', '.join(entry.entity_ids)}]"
            sections.setdefault(label, []).append(line)

        parts: list[str] = ["**Recalled from memory:**"]
        for label, lines in sections.items():
            parts.append(f"\n_{label}_")
            parts.extend(lines)

        return "\n".join(parts)

    def _trim_to_budget(self, entries: list[MemoryEntry]) -> list[MemoryEntry]:
        """Keep entries until the token budget is exhausted."""
        budget = self._token_budget * _CHARS_PER_TOKEN
        kept: list[MemoryEntry] = []
        used = 0
        for entry in entries:
            cost = len(entry.key) + len(entry.value) + 20
            if used + cost > budget:
                break
            kept.append(entry)
            used += cost
        return kept


def _namespace_label(ns: str) -> str:
    labels = {
        MemoryNamespace.FEEDBACK: "Corrections & feedback",
        MemoryNamespace.REFERENCE: "Reference knowledge",
        MemoryNamespace.EPISODIC: "Prior sessions",
        MemoryNamespace.PLAN: "Active plans",
    }
    return labels.get(ns, ns.title())  # type: ignore[arg-type]
