"""IngestionService — schema-driven entity extraction from uploaded documents.

Report type detection uses a two-tier approach:

  1. Structural (fast): scored column fingerprinting via the adapter registry.
     Returns events when a known adapter claims the document.

  2. Semantic (LLM fallback): when structural detection returns nothing, the
     optional report_classifier agent is asked to identify the report type
     from column names and sample rows.  If that also fails, the document
     falls back to generic ingest (raw rows stored as KB entities).

Ingestion is dispatched through the adapter registry.  Each source platform
is a self-contained adapter that emits canonical IngestionEvents.  The engine
applies those events to KnowledgeStore and PropertyStore with no knowledge of
the source format.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import structlog

from remi.documents.types import Document
from remi.graph.stores import KnowledgeStore
from remi.graph.types import Entity
from remi.ingestion.adapters.registry import get_adapter_events
from remi.ingestion.base import IngestionResult
from remi.ingestion.engine import apply_events
from remi.ingestion.generic import ingest_generic
from remi.ingestion.managers import ManagerResolver
from remi.portfolio.protocols import PropertyStore

ClassifyFn = Callable[[Document], Awaitable[str | None]]

logger = structlog.get_logger(__name__)


class IngestionService:
    """Extracts entities and relationships from documents into a KnowledgeStore
    and upserts typed domain models into PropertyStore."""

    def __init__(
        self,
        knowledge_store: KnowledgeStore,
        property_store: PropertyStore,
        classify_fn: ClassifyFn | None = None,
    ) -> None:
        self._kb = knowledge_store
        self._ps = property_store
        self._classify_fn = classify_fn
        self._manager_resolver = ManagerResolver(
            manager_repo=property_store,
            portfolio_repo=property_store,
        )

    async def ingest(
        self,
        doc: Document,
        *,
        manager: str | None = None,
    ) -> IngestionResult:
        namespace = f"doc:{doc.id}"
        result = IngestionResult(document_id=doc.id)

        # Resolve upload-level portfolio override
        upload_portfolio_id: str | None = None
        if manager:
            upload_portfolio_id = await self._manager_resolver.ensure_manager(manager)

        # Try structural adapter first
        adapter_result = get_adapter_events(doc.id, doc.column_names, doc.rows)

        if adapter_result is not None:
            platform, events = adapter_result
            # Use the report_type from the first event's SourceRef
            if events:
                result.report_type = events[0].source.report_type
            await apply_events(
                events,
                namespace=namespace,
                kb=self._kb,
                ps=self._ps,
                manager_resolver=self._manager_resolver,
                result=result,
                upload_portfolio_id=upload_portfolio_id,
            )
        else:
            # LLM fallback for unrecognised documents
            llm_type = await self._classify_with_llm(doc)
            if llm_type:
                result.report_type = llm_type
                logger.info(
                    "report_type_from_llm",
                    doc_id=doc.id,
                    llm_type=llm_type,
                )
            await ingest_generic(doc, namespace, result, self._kb)

        # Write document-level KB entity regardless of path
        await self._kb.put_entity(
            Entity(
                entity_id=f"document:{doc.id}",
                entity_type="document",
                namespace=namespace,
                properties={
                    "filename": doc.filename,
                    "content_type": doc.content_type,
                    "row_count": doc.row_count,
                    "columns": doc.column_names,
                    "report_type": result.report_type,
                },
            )
        )

        logger.info(
            "ingestion_complete",
            doc_id=doc.id,
            report_type=result.report_type,
            entities=result.entities_created,
            relationships=result.relationships_created,
            ambiguous=len(result.ambiguous_rows),
        )
        return result

    async def _classify_with_llm(self, doc: Document) -> str | None:
        if self._classify_fn is None:
            return None
        return await self._classify_fn(doc)
