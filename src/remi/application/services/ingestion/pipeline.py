"""ingestion/pipeline.py — full document ingestion pipeline.

Orchestrates the complete inbound data flow:
  upload → parse → extract → persist → embed

For non-tabular documents (PDF, DOCX, TXT, images), the pipeline skips
entity extraction and only runs save + embedding.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import structlog

from remi.application.core.protocols import (
    DocumentParser,
    DocumentRepository,
    ParsedDocument,
)
from remi.application.services.embedding.pipeline import EmbeddingPipeline
from remi.application.services.ingestion.rules import extract_rows
from remi.application.services.ingestion.service import IngestionService

_log = structlog.get_logger(__name__)


@dataclass
class IngestResult:
    doc: ParsedDocument
    report_type: str
    entities_extracted: int
    relationships_extracted: int
    ambiguous_rows: int
    rows_accepted: int = 0
    rows_rejected: int = 0
    rows_skipped: int = 0
    validation_warnings: list[str] = field(default_factory=list)
    entities_embedded: int = 0
    pipeline_warnings: list[str] = field(default_factory=list)


class DocumentIngestService:
    """Orchestrates document upload → parse → ingest → enrich → reason."""

    def __init__(
        self,
        document_repo: DocumentRepository,
        document_parser: DocumentParser,
        ingestion_service: IngestionService,
        embedding_pipeline: EmbeddingPipeline,
        metadata_skip_patterns: tuple[str, ...] = (),
    ) -> None:
        self._doc_repo = document_repo
        self._doc_parser = document_parser
        self._ingestion = ingestion_service
        self._embedding_pipeline = embedding_pipeline
        self._skip_patterns = metadata_skip_patterns

    async def ingest_upload(
        self,
        filename: str,
        content: bytes,
        content_type: str,
        *,
        manager: str | None = None,
        run_pipelines: bool = True,
    ) -> IngestResult:
        doc = self._doc_parser.parse(
            filename, content, content_type,
            extra_skip_patterns=self._skip_patterns,
        )

        await self._doc_repo.save(doc)

        if doc.kind != "tabular":
            return await self._reference_path(doc, run_pipelines=run_pipelines)

        result = await self._rules_path(doc, manager=manager)
        if result is None:
            result = await self._llm_path(doc, manager=manager)

        doc_with_meta = ParsedDocument(
            id=doc.id,
            filename=doc.filename,
            content_type=doc.content_type,
            kind=doc.kind,
            column_names=doc.column_names,
            rows=doc.rows,
            row_count=doc.row_count,
            chunks=doc.chunks,
            raw_text=doc.raw_text,
            page_count=doc.page_count,
            tags=doc.tags,
            size_bytes=doc.size_bytes,
            effective_date=doc.effective_date,
            metadata={**doc.metadata, "report_type": result.report_type},
        )
        await self._doc_repo.save(doc_with_meta)
        result.doc = doc_with_meta

        if run_pipelines:
            await self._run_downstream_pipelines(result, doc_with_meta)

        return result

    async def _reference_path(
        self,
        doc: ParsedDocument,
        *,
        run_pipelines: bool = True,
    ) -> IngestResult:
        """Handle text/image documents — skip entity extraction, embed only."""
        result = IngestResult(
            doc=doc,
            report_type=doc.kind,
            entities_extracted=0,
            relationships_extracted=0,
            ambiguous_rows=0,
        )

        if run_pipelines:
            try:
                embed_result = await self._embedding_pipeline.run_full()
                result.entities_embedded = embed_result.embedded
                _log.info(
                    "reference_doc_embedded",
                    filename=doc.filename,
                    kind=doc.kind,
                    embedded=embed_result.embedded,
                )
            except Exception as exc:
                result.pipeline_warnings.append(f"embedding_pipeline: {exc}")
                _log.warning("reference_doc_embed_failed", exc_info=True)

        return result

    async def _rules_path(
        self,
        doc: ParsedDocument,
        *,
        manager: str | None = None,
    ) -> IngestResult | None:
        """Try deterministic column-mapping extraction — zero LLM calls."""
        match = extract_rows(doc.column_names, doc.rows)
        if match is None:
            return None

        report_type, mapped_rows = match
        _log.info(
            "rules_path_matched",
            filename=doc.filename,
            report_type=report_type,
            rows=len(mapped_rows),
        )

        ingestion_result = await self._ingestion.ingest_mapped_rows(
            doc,
            report_type=report_type,
            rows=mapped_rows,
            manager=manager,
        )

        validation_warnings = [
            f"row {w.row_index} ({w.row_type}).{w.field}: {w.issue}"
            for w in ingestion_result.validation_warnings
        ] + [
            f"row {w.row_index} ({w.row_type}).{w.field}: {w.issue}"
            for w in ingestion_result.persist_errors
        ]

        return IngestResult(
            doc=doc,
            report_type=report_type,
            entities_extracted=ingestion_result.entities_created,
            relationships_extracted=ingestion_result.relationships_created,
            ambiguous_rows=len(ingestion_result.ambiguous_rows),
            rows_accepted=ingestion_result.rows_accepted,
            rows_rejected=ingestion_result.rows_rejected,
            rows_skipped=ingestion_result.rows_skipped,
            validation_warnings=validation_warnings,
        )

    async def _llm_path(
        self,
        doc: ParsedDocument,
        *,
        manager: str | None = None,
    ) -> IngestResult:
        """Run the LLM extraction pipeline."""
        ingestion_result = await self._ingestion.ingest(doc, manager=manager)

        validation_warnings = [
            f"row {w.row_index} ({w.row_type}).{w.field}: {w.issue}"
            for w in ingestion_result.validation_warnings
        ] + [
            f"row {w.row_index} ({w.row_type}).{w.field}: {w.issue}"
            for w in ingestion_result.persist_errors
        ]

        return IngestResult(
            doc=doc,
            report_type=ingestion_result.report_type,
            entities_extracted=ingestion_result.entities_created,
            relationships_extracted=ingestion_result.relationships_created,
            ambiguous_rows=len(ingestion_result.ambiguous_rows),
            rows_accepted=ingestion_result.rows_accepted,
            rows_rejected=ingestion_result.rows_rejected,
            rows_skipped=ingestion_result.rows_skipped,
            validation_warnings=validation_warnings,
        )

    async def _run_downstream_pipelines(
        self,
        result: IngestResult,
        doc: ParsedDocument,
    ) -> None:
        """Run embedding pipeline after ingestion.

        TODO: replace with delta — currently re-embeds all entities
        """
        try:
            embed_result = await self._embedding_pipeline.run_full()
            result.entities_embedded = embed_result.embedded
            _log.info(
                "embedding_pipeline_complete",
                embedded=embed_result.embedded,
                by_type=embed_result.by_type,
            )
        except Exception as exc:
            result.pipeline_warnings.append(f"embedding_pipeline: {exc}")
            _log.warning("embedding_pipeline_failed", exc_info=True)
