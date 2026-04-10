"""Document upload + inline ingestion — parse, match, persist, done.

Known formats (vocabulary match) are fully ingested synchronously:
parse → vocab match → column map → validate → persist → complete.

Unknown formats (vocab miss) return ``status="processing"`` and the
caller dispatches the ingester agent for LLM-assisted classification.
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import date

import structlog

from remi.agent.documents import ContentStore
from remi.agent.documents.adapters.parsers import parse_document
from remi.agent.documents.types import DocumentKind
from remi.agent.events import EventBus
from remi.application.core.models import Document, DocumentType, ReportType
from remi.application.core.models.date_range import DateRange
from remi.application.core.protocols import DocumentIngester, PropertyStore, UploadResult
from remi.application.ingestion.models import IngestionResult
from remi.application.ingestion.operations import run_deterministic_pipeline
from remi.application.ingestion.rules import resolve_manager_from_metadata, resolve_report_dates
from remi.application.ingestion.vocab import match_columns

_log = structlog.get_logger(__name__)


class DocumentIngestService(DocumentIngester):
    """Parse, dedup, and ingest uploaded documents.

    For tabular files with recognised columns (vocabulary hit), the full
    extraction pipeline runs inline — zero LLM calls, sub-second response.

    For genuinely unknown formats, returns ``status="processing"`` so the
    caller can dispatch the LLM-assisted ingester agent.
    """

    def __init__(
        self,
        content_store: ContentStore,
        property_store: PropertyStore,
        event_bus: EventBus | None = None,
        metadata_skip_patterns: tuple[str, ...] = (),
        section_labels: frozenset[str] = frozenset(),
    ) -> None:
        self._content_store = content_store
        self._ps = property_store
        self._event_bus = event_bus
        self._skip_patterns = metadata_skip_patterns
        self._section_labels = section_labels

    @property
    def content_store(self) -> ContentStore:
        return self._content_store

    async def ingest_upload(
        self,
        filename: str,
        content: bytes,
        content_type: str,
        *,
        manager: str | None = None,
        unit_id: str | None = None,
        property_id: str | None = None,
        lease_id: str | None = None,
        document_type: str | None = None,
    ) -> UploadResult:
        # ── Step 1: Parse ────────────────────────────────────────────
        doc_content = await asyncio.to_thread(
            parse_document,
            filename,
            content,
            content_type,
            extra_skip_patterns=self._skip_patterns,
            section_labels=self._section_labels,
        )
        doc_content.size_bytes = len(content)

        # ── Step 1b: Extract temporal spine ──────────────────────────
        # Done before dedup so every document record carries dates,
        # regardless of which code path completes the upload.
        meta = doc_content.metadata or {}
        report_dates = resolve_report_dates(meta, filename)

        # ── Step 2: Dedup ────────────────────────────────────────────
        content_hash = hashlib.sha256(content).hexdigest()
        existing = await self._ps.find_by_content_hash(content_hash)
        if existing is not None:
            return UploadResult(
                doc=_build_doc(
                    doc_content,
                    content_hash=content_hash,
                    document_type=document_type,
                    unit_id=unit_id,
                    property_id=property_id,
                    lease_id=lease_id,
                ),
                duplicate_of=existing,
                report_type=existing.report_type.value,
            )

        # ── Step 3: Save content + document record ───────────────────
        await self._content_store.save(doc_content)

        doc = _build_doc(
            doc_content,
            content_hash=content_hash,
            document_type=document_type,
            unit_id=unit_id,
            property_id=property_id,
            lease_id=lease_id,
            effective_date=report_dates.effective_date,
            coverage=report_dates.coverage,
        )
        await self._ps.upsert_document(doc)

        # Non-tabular → done immediately.
        if doc_content.kind != DocumentKind.tabular:
            return UploadResult(doc=doc, report_type="unknown")

        if not doc_content.column_names or not doc_content.rows:
            return UploadResult(
                doc=doc,
                pipeline_warnings=["No columns or rows found in document"],
            )

        # ── Step 4: Vocabulary match ─────────────────────────────────
        vocab = match_columns(doc_content.column_names)

        if not vocab.should_proceed:
            _log.info(
                "vocab_miss_dispatch_to_agent",
                doc_id=doc_content.id,
                filename=filename,
                report_type=vocab.report_type,
                unrecognized=vocab.unrecognized,
            )
            return UploadResult(doc=doc, status="processing")

        # ── Step 5: Run deterministic pipeline (inline) ──────────────
        manager_name, scope = resolve_manager_from_metadata(meta)

        result = IngestionResult(
            document_id=doc_content.id,
            report_type=ReportType.UNKNOWN,
            as_of_date=report_dates.effective_date,
        )

        extract_data = {
            "report_type": vocab.report_type,
            "primary_entity_type": vocab.primary_entity_type,
            "column_map": vocab.column_map,
            "platform": "appfolio",
            "manager": manager_name,
            "scope": scope,
            "as_of_date": report_dates.effective_date,
        }

        _log.info(
            "inline_ingestion_start",
            doc_id=doc_content.id,
            filename=filename,
            report_type=vocab.report_type,
            columns=doc_content.column_names,
            row_count=doc_content.row_count,
        )

        try:
            await run_deterministic_pipeline(
                ps=self._ps,
                doc_id=doc_content.id,
                platform="appfolio",
                result=result,
                all_rows=doc_content.rows,
                extract_data=extract_data,
            )
        except Exception:
            _log.warning(
                "inline_ingestion_failed",
                doc_id=doc_content.id,
                exc_info=True,
            )
            return UploadResult(
                doc=doc,
                status="processing",
                pipeline_warnings=["Inline ingestion failed; dispatching agent"],
            )

        # ── Step 6: Finalize ─────────────────────────────────────────
        try:
            rt = ReportType(vocab.report_type)
        except ValueError:
            rt = ReportType.UNKNOWN

        updated_doc = doc.model_copy(
            update={
                "report_type": rt,
                "report_manager": manager_name,
                "effective_date": report_dates.effective_date,
                "coverage": report_dates.coverage,
            }
        )
        await self._ps.upsert_document(updated_doc)

        if self._event_bus:
            try:
                from remi.agent.events import DomainEvent

                await self._event_bus.publish(
                    DomainEvent(
                        topic="ingestion.complete",
                        source="upload_service",
                        payload={
                            "document_id": doc_content.id,
                            "report_type": rt.value,
                            "as_of_date": result.as_of_date.isoformat() if result.as_of_date else None,
                            "entities_extracted": result.entities_created,
                            "rows_accepted": result.rows_accepted,
                            "rows_rejected": result.rows_rejected,
                            "graph_changed": result.entities_created > 0,
                            "review_notes": vocab.review_notes,
                        },
                    )
                )
            except Exception:
                _log.warning(
                    "event_publish_failed",
                    topic="ingestion.complete",
                    exc_info=True,
                )

        _log.info(
            "inline_ingestion_complete",
            doc_id=doc_content.id,
            report_type=rt.value,
            entities=result.entities_created,
            relationships=result.relationships_created,
            rows_accepted=result.rows_accepted,
            rows_rejected=result.rows_rejected,
        )

        return UploadResult(
            doc=updated_doc,
            report_type=rt.value,
            entities_extracted=result.entities_created,
            relationships_extracted=result.relationships_created,
            rows_accepted=result.rows_accepted,
            rows_rejected=result.rows_rejected,
            rows_skipped=result.rows_skipped,
            review_items=result.review_items,
            validation_warnings=[
                f"row {w.row_index} ({w.row_type}).{w.field}: {w.issue}"
                for w in result.validation_warnings
            ],
        )


def _build_doc(
    content,
    *,
    content_hash: str,
    report_type: ReportType = ReportType.UNKNOWN,
    document_type: str | None = None,
    unit_id: str | None = None,
    property_id: str | None = None,
    lease_id: str | None = None,
    manager_id: str | None = None,
    report_manager: str | None = None,
    effective_date: date | None = None,
    coverage: DateRange | None = None,
) -> Document:
    dt = DocumentType.REPORT
    if document_type:
        try:
            dt = DocumentType(document_type)
        except ValueError:
            dt = DocumentType.OTHER
    return Document(
        id=content.id,
        filename=content.filename,
        content_type=content.content_type,
        content_hash=content_hash,
        document_type=dt,
        kind=content.kind.value if hasattr(content.kind, "value") else str(content.kind),
        page_count=content.page_count,
        chunk_count=len(content.chunks),
        row_count=content.row_count,
        size_bytes=content.size_bytes,
        tags=content.tags,
        report_type=report_type,
        unit_id=unit_id,
        property_id=property_id,
        lease_id=lease_id,
        manager_id=manager_id,
        report_manager=report_manager,
        effective_date=effective_date,
        coverage=coverage,
    )
