"""IngestionService — schema-driven entity extraction from uploaded documents.

Report type detection uses a two-tier approach:

  1. Structural (fast): scored column fingerprinting via detect_report_type_scored().
     Returns the best-matching known type when confidence >= threshold.

  2. Semantic (LLM fallback): when structural detection returns UNKNOWN or scores
     below the threshold, the optional report_classifier agent is asked to identify
     the report type from column names and sample rows.

Ingestion is dispatched through the schema registry (REPORT_SCHEMAS). Each
report type is a declarative ReportSchema — no per-type handler files. Unknown
types fall back to a minimal generic ingest that stores raw rows as KB entities.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import structlog

from remi.documents.appfolio_schema import (
    AppFolioReportType,
    detect_report_type_scored,
)
from remi.knowledge.ingestion.base import IngestionResult
from remi.knowledge.ingestion.generic import ingest_generic
from remi.knowledge.ingestion.managers import ManagerResolver
from remi.knowledge.ingestion.schema import REPORT_SCHEMAS, ingest_report
from remi.models.documents import Document
from remi.models.memory import Entity, KnowledgeStore
from remi.models.properties import PropertyStore

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

        structural_type, confidence = detect_report_type_scored(doc.column_names)



        if structural_type != AppFolioReportType.UNKNOWN:
            report_type = structural_type
        else:
            llm_type = await self._classify_with_llm(doc)
            report_type = llm_type or AppFolioReportType.UNKNOWN
            if report_type != AppFolioReportType.UNKNOWN:
                logger.info(
                    "report_type_from_llm",
                    doc_id=doc.id,
                    structural_confidence=confidence,
                    llm_type=llm_type,
                )

        result = IngestionResult(document_id=doc.id, report_type=report_type)

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
                    "report_type": report_type,
                    "detection_confidence": confidence,
                },
            )
        )
        result.entities_created += 1

        upload_portfolio_id: str | None = None
        if manager:
            upload_portfolio_id = await self._manager_resolver.ensure_manager(manager)

        schema = REPORT_SCHEMAS.get(report_type)
        if schema:
            await ingest_report(
                doc_id=doc.id,
                rows=doc.rows,
                namespace=namespace,
                schema=schema,
                kb=self._kb,
                ps=self._ps,
                manager_resolver=self._manager_resolver,
                result=result,
                upload_portfolio_id=upload_portfolio_id,
            )
        else:
            logger.info(
                "ingest_fallback_to_generic",
                doc_id=doc.id,
                report_type=report_type,
            )
            await ingest_generic(doc, namespace, result, self._kb)

        logger.info(
            "ingestion_complete",
            doc_id=doc.id,
            report_type=report_type,
            detection_confidence=confidence,
            entities=result.entities_created,
            relationships=result.relationships_created,
            ambiguous=len(result.ambiguous_rows),
        )
        return result

    async def _classify_with_llm(self, doc: Document) -> str | None:
        if self._classify_fn is None:
            return None
        return await self._classify_fn(doc)
