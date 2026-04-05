"""Adapter implementations for application/core infrastructure ports.

Each class bridges an application-level port (defined in core/protocols.py)
to the corresponding agent/ primitive.  Built by the container; injected
into services so they never import agent/ directly.
"""

from __future__ import annotations

from typing import Any

import structlog

from remi.agent.documents import Document, DocumentKind, DocumentStore, TextChunk, parse_document
from remi.agent.graph import (
    Entity,
    FactProvenance,
    KnowledgeGraph,
    KnowledgeProvenance,
    KnowledgeStore,
    Relationship,
)
from remi.agent.vectors import (
    Embedder,
    EmbeddingRecord,
    EmbeddingRequest,
    SearchResult,
    VectorStore,
)
from remi.application.core.protocols import (
    DocumentParser,
    DocumentRepository,
    EmbedRequest,
    KBEntity,
    KBRelationship,
    KnowledgeReader,
    KnowledgeWriter,
    ParsedDocument,
    ParsedTextChunk,
    TextIndexer,
    TextSearchHit,
    VectorSearch,
)

_log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Knowledge graph
# ---------------------------------------------------------------------------


class KnowledgeStoreWriter(KnowledgeWriter):
    """Adapts ``agent.graph.KnowledgeStore`` to the ``KnowledgeWriter`` port."""

    def __init__(self, store: KnowledgeStore) -> None:
        self._store = store

    @property
    def inner(self) -> KnowledgeStore:
        return self._store

    async def put_entity(self, entity: KBEntity) -> None:
        await self._store.put_entity(
            Entity(
                entity_id=entity.entity_id,
                entity_type=entity.entity_type,
                namespace=entity.namespace,
                properties=entity.properties,
                metadata=entity.metadata,
            )
        )

    async def get_entity(self, namespace: str, entity_id: str) -> KBEntity | None:
        e = await self._store.get_entity(namespace, entity_id)
        if e is None:
            return None
        return KBEntity(
            entity_id=e.entity_id,
            entity_type=e.entity_type,
            namespace=e.namespace,
            properties=dict(e.properties),
        )

    async def put_relationship(self, rel: KBRelationship) -> None:
        await self._store.put_relationship(
            Relationship(
                source_id=rel.source_id,
                target_id=rel.target_id,
                relation_type=rel.relation_type,
                namespace=rel.namespace,
            )
        )


class KnowledgeStoreReader(KnowledgeReader):
    """Adapts ``agent.graph.KnowledgeStore`` to the ``KnowledgeReader`` port."""

    def __init__(self, store: KnowledgeStore) -> None:
        self._store = store

    @property
    def inner(self) -> KnowledgeStore:
        return self._store

    async def find_entities(
        self,
        namespace: str,
        entity_type: str | None = None,
        *,
        limit: int = 20,
    ) -> list[KBEntity]:
        entities = await self._store.find_entities(
            namespace, entity_type=entity_type, limit=limit,
        )
        return [
            KBEntity(
                entity_id=e.entity_id,
                entity_type=e.entity_type,
                namespace=e.namespace,
                properties=dict(e.properties),
            )
            for e in entities
        ]

    async def list_namespaces(self) -> list[str]:
        return await self._store.list_namespaces()


# ---------------------------------------------------------------------------
# Document parsing & storage
# ---------------------------------------------------------------------------


def _doc_to_parsed(doc: Document) -> ParsedDocument:
    return ParsedDocument(
        id=doc.id,
        filename=doc.filename,
        content_type=doc.content_type,
        kind=doc.kind.value,
        column_names=doc.column_names,
        rows=doc.rows,
        row_count=doc.row_count,
        chunks=[
            ParsedTextChunk(index=c.index, text=c.text, page=c.page)
            for c in doc.chunks
        ],
        raw_text=doc.raw_text,
        page_count=doc.page_count,
        tags=list(doc.tags),
        size_bytes=doc.size_bytes,
        effective_date=doc.effective_date,
        metadata=dict(doc.metadata),
    )


def _parsed_to_doc(pd: ParsedDocument) -> Document:
    return Document(
        id=pd.id,
        filename=pd.filename,
        content_type=pd.content_type,
        kind=DocumentKind(pd.kind),
        column_names=pd.column_names,
        rows=pd.rows,
        row_count=pd.row_count,
        chunks=[
            TextChunk(index=c.index, text=c.text, page=c.page)
            for c in pd.chunks
        ],
        raw_text=pd.raw_text,
        page_count=pd.page_count,
        tags=list(pd.tags),
        size_bytes=pd.size_bytes,
        metadata=pd.metadata,
    )


class AgentDocumentParser(DocumentParser):
    """Adapts ``agent.documents.parse_document`` to ``DocumentParser``."""

    def parse(
        self,
        filename: str,
        content: bytes,
        content_type: str,
        *,
        extra_skip_patterns: tuple[str, ...] = (),
    ) -> ParsedDocument:
        doc = parse_document(
            filename, content, content_type,
            extra_skip_patterns=extra_skip_patterns,
        )
        return _doc_to_parsed(doc)


class AgentDocumentRepository(DocumentRepository):
    """Adapts ``agent.documents.DocumentStore`` to ``DocumentRepository``."""

    def __init__(self, store: DocumentStore) -> None:
        self._store = store

    @property
    def inner(self) -> DocumentStore:
        return self._store

    async def save(self, doc: ParsedDocument) -> None:
        await self._store.save(_parsed_to_doc(doc))

    async def get(self, doc_id: str) -> ParsedDocument | None:
        doc = await self._store.get(doc_id)
        if doc is None:
            return None
        return _doc_to_parsed(doc)

    async def list_documents(self) -> list[ParsedDocument]:
        docs = await self._store.list_documents()
        return [_doc_to_parsed(d) for d in docs]

    async def search_documents(
        self,
        *,
        query: str | None = None,
        kind: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
    ) -> list[ParsedDocument]:
        dk = DocumentKind(kind) if kind else None
        docs = await self._store.search_documents(
            query=query, kind=dk, tags=tags, limit=limit,
        )
        return [_doc_to_parsed(d) for d in docs]

    async def update_tags(self, doc_id: str, tags: list[str]) -> bool:
        return await self._store.update_tags(doc_id, tags)


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

    def _to_hit(self, r: SearchResult) -> TextSearchHit:
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
            query, fields=fields, limit=limit,
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
    "AgentDocumentParser",
    "AgentDocumentRepository",
    "AgentTextIndexer",
    "AgentVectorSearch",
    "KnowledgeStoreReader",
    "KnowledgeStoreWriter",
]
