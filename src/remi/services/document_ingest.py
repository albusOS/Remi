"""DocumentIngestService — upload, parse, ingest, and enrich documents.

Orchestrates the full document ingestion pipeline:
  parse → persist → structured ingest → LLM enrich → snapshot →
  signal pipeline (rule + statistical) → pattern detection → embed

LLM enrichment (previously in knowledge/enrichment.py) is merged here —
it is a pipeline step, not reusable knowledge logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import structlog

from remi.documents.parsers import parse_csv, parse_excel
from remi.knowledge.composite import CompositeProducer
from remi.knowledge.ingestion import IngestionService
from remi.knowledge.pattern_detector import PatternDetector
from remi.models.documents import Document, DocumentStore
from remi.models.memory import KnowledgeStore
from remi.models.properties import PropertyStore
from remi.services.enrichment import EnrichFn
from remi.services.snapshots import SnapshotService
from remi.vectors.pipeline import EmbeddingPipeline

_log = structlog.get_logger(__name__)

_CSV_TYPES = {"text/csv", "application/csv"}
_EXCEL_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
}


@dataclass
class IngestResult:
    doc: Document
    report_type: str
    entities_extracted: int
    relationships_extracted: int
    ambiguous_rows: int
    signals_produced: int = 0
    hypotheses_proposed: int = 0
    entities_embedded: int = 0
    pipeline_warnings: list[str] = field(default_factory=list)


class DocumentIngestService:
    """Orchestrates document upload → parse → ingest → enrich → reason."""

    def __init__(
        self,
        document_store: DocumentStore,
        ingestion_service: IngestionService,
        knowledge_store: KnowledgeStore,
        property_store: PropertyStore,
        snapshot_service: SnapshotService,
        signal_pipeline: CompositeProducer,
        pattern_detector: PatternDetector,
        embedding_pipeline: EmbeddingPipeline,
        enrich_fn: EnrichFn | None = None,
    ) -> None:
        self._doc_store = document_store
        self._ingestion = ingestion_service
        self._knowledge_store = knowledge_store
        self._property_store = property_store
        self._snapshot_service = snapshot_service
        self._signal_pipeline = signal_pipeline
        self._pattern_detector = pattern_detector
        self._embedding_pipeline = embedding_pipeline
        self._enrich_fn = enrich_fn

    async def ingest_upload(
        self,
        filename: str,
        content: bytes,
        content_type: str,
        *,
        manager: str | None = None,
        run_pipelines: bool = True,
    ) -> IngestResult:
        ct = content_type.lower()
        if ct in _CSV_TYPES or filename.lower().endswith(".csv"):
            doc = parse_csv(filename, content)
        elif ct in _EXCEL_TYPES or filename.lower().endswith((".xlsx", ".xls")):
            doc = parse_excel(filename, content)
        else:
            raise ValueError(f"Unsupported file type: {ct}. Supported: CSV, Excel (.xlsx).")

        await self._doc_store.save(doc)

        ingestion_result = await self._ingestion.ingest(doc, manager=manager)

        doc_with_meta = doc.model_copy(
            update={"metadata": {**doc.metadata, "report_type": ingestion_result.report_type}}
        )
        await self._doc_store.save(doc_with_meta)

        enriched_entities = 0
        enriched_rels = 0
        if self._enrich_fn and ingestion_result.ambiguous_rows:
            enriched_entities, enriched_rels = await self._enrich_fn(
                ingestion_result.ambiguous_rows,
                doc,
                self._knowledge_store,
            )

        signals_produced = 0
        hypotheses_proposed = 0
        entities_embedded = 0
        pipeline_warnings: list[str] = []

        if run_pipelines:
            try:
                await self._snapshot_service.capture(effective_date=doc_with_meta.effective_date)
                _log.info("performance_snapshot_captured")
            except Exception as exc:
                pipeline_warnings.append(f"snapshot_capture: {exc}")
                _log.warning("snapshot_capture_failed", exc_info=True)

            try:
                pipeline_result = await self._signal_pipeline.run_all()
                signals_produced = pipeline_result.produced
                _log.info(
                    "signal_pipeline_complete",
                    signals_produced=pipeline_result.produced,
                    sources={k: v.produced for k, v in pipeline_result.per_source.items()},
                )
            except Exception as exc:
                pipeline_warnings.append(f"signal_pipeline: {exc}")
                _log.warning("signal_pipeline_failed", exc_info=True)

            try:
                detector_result = await self._pattern_detector.run()
                hypotheses_proposed = detector_result.proposed
                _log.info(
                    "pattern_detection_complete",
                    hypotheses_proposed=detector_result.proposed,
                    types_scanned=detector_result.types_scanned,
                )
            except Exception as exc:
                pipeline_warnings.append(f"pattern_detection: {exc}")
                _log.warning("pattern_detection_failed", exc_info=True)

            try:
                embed_result = await self._embedding_pipeline.run_full()
                entities_embedded = embed_result.embedded
                _log.info(
                    "embedding_pipeline_complete",
                    embedded=embed_result.embedded,
                    by_type=embed_result.by_type,
                )
            except Exception as exc:
                pipeline_warnings.append(f"embedding_pipeline: {exc}")
                _log.warning("embedding_pipeline_failed", exc_info=True)

        return IngestResult(
            doc=doc_with_meta,
            report_type=ingestion_result.report_type,
            entities_extracted=ingestion_result.entities_created + enriched_entities,
            relationships_extracted=ingestion_result.relationships_created + enriched_rels,
            ambiguous_rows=len(ingestion_result.ambiguous_rows),
            signals_produced=signals_produced,
            hypotheses_proposed=hypotheses_proposed,
            entities_embedded=entities_embedded,
            pipeline_warnings=pipeline_warnings,
        )
