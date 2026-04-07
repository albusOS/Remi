"""Adapter implementations for application/core infrastructure ports.

Each class bridges an application-level port (defined in core/protocols.py)
to the corresponding agent/ primitive.  Built by the container; injected
into services so they never import agent/ directly.
"""

from __future__ import annotations

from typing import Any

import structlog

from remi.agent.vectors import (
    Embedder,
    EmbeddingRecord,
    VectorStore,
)
from remi.application.core.protocols import (
    EmbedRequest,
    TextIndexer,
    TextSearchHit,
    VectorSearch,
)

_log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Embedding / vector search
# ---------------------------------------------------------------------------


class AgentTextIndexer(TextIndexer):
    """Adapts ``Embedder`` + ``VectorStore`` to ``TextIndexer``."""

    def __init__(self, embedder: Embedder, vector_store: VectorStore) -> None:
        self._embedder = embedder
        self._vs = vector_store

    async def index_many(self, requests: list[EmbedRequest]) -> int:
        if not requests:
            return 0

        indexed = 0
        batch_size = 100
        for i in range(0, len(requests), batch_size):
            batch = requests[i : i + batch_size]
            try:
                vectors = await self._embedder.embed([r.text for r in batch])
            except Exception:
                _log.warning("index_batch_embed_failed", batch_start=i, exc_info=True)
                continue

            records = [
                EmbeddingRecord(
                    id=req.id,
                    text=req.text,
                    vector=vec,
                    source_entity_id=req.source_entity_id,
                    source_entity_type=req.source_entity_type,
                    source_field=req.source_field,
                    metadata=req.metadata,
                )
                for req, vec in zip(batch, vectors, strict=False)
            ]
            await self._vs.put_many(records)
            indexed += len(records)

        return indexed


class AgentVectorSearch(VectorSearch):
    """Adapts ``VectorStore`` + ``Embedder`` to ``VectorSearch``."""

    def __init__(self, vector_store: VectorStore, embedder: Embedder) -> None:
        self._vs = vector_store
        self._embedder = embedder

    def _to_hit(self, r: Any) -> TextSearchHit:
        return TextSearchHit(
            entity_id=r.record.source_entity_id,
            entity_type=r.record.source_entity_type,
            text=r.record.text,
            score=r.score,
            metadata=r.record.metadata,
        )

    async def keyword_search(
        self,
        query: str,
        *,
        fields: list[str] | None = None,
        limit: int = 10,
    ) -> list[TextSearchHit]:
        results = await self._vs.metadata_text_search(
            query,
            fields=fields,
            limit=limit,
        )
        return [self._to_hit(r) for r in results]

    async def semantic_search(
        self,
        query: str,
        *,
        limit: int = 10,
        min_score: float = 0.0,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[TextSearchHit]:
        vector = await self._embedder.embed_one(query)
        results = await self._vs.search(
            vector,
            limit=limit,
            min_score=min_score,
            metadata_filter=metadata_filter,
        )
        return [self._to_hit(r) for r in results]


__all__ = [
    "AgentTextIndexer",
    "AgentVectorSearch",
]
