"""Document ingestion host — parse, dedup, save, dispatch.

Phase 1 (synchronous, this module): parse the file, hash it for dedup,
save content, persist a Document record, return ``status="processing"``.

Phase 2 (asynchronous, ingester agent): the caller dispatches the ingester
agent via ``TaskSupervisor``.  The agent classifies the report, maps columns,
and runs the deterministic extraction pipeline.  It publishes
``ingestion.complete`` when done.

There is no synchronous entity-extraction path.  Column mapping is the
agent's job — it handles AppFolio, Yardi, Buildium, and any custom
spreadsheet without a profile list.
"""

from __future__ import annotations

import asyncio
import hashlib

import structlog

from remi.agent.documents import ContentStore
from remi.agent.documents.adapters.parsers import parse_document
from remi.agent.documents.types import DocumentKind
from remi.agent.events import EventBus
from remi.application.core.models import Document, DocumentType, ReportType
from remi.application.core.protocols import DocumentIngester, PropertyStore, UploadResult

_log = structlog.get_logger(__name__)


class DocumentIngestService(DocumentIngester):
    """Parse, dedup, and save uploaded documents.

    Always returns ``status="processing"`` for tabular files — the caller
    dispatches the ingester agent to finish extraction.  Non-tabular files
    (PDFs, text) return immediately with no further processing.
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
        doc_content = await asyncio.to_thread(
            parse_document,
            filename,
            content,
            content_type,
            extra_skip_patterns=self._skip_patterns,
            section_labels=self._section_labels,
        )
        doc_content.size_bytes = len(content)

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

        await self._content_store.save(doc_content)

        doc = _build_doc(
            doc_content,
            content_hash=content_hash,
            document_type=document_type,
            unit_id=unit_id,
            property_id=property_id,
            lease_id=lease_id,
        )
        await self._ps.upsert_document(doc)

        if doc_content.kind != DocumentKind.tabular:
            return UploadResult(doc=doc, report_type="unknown")

        if not doc_content.column_names or not doc_content.rows:
            return UploadResult(
                doc=doc,
                pipeline_warnings=["No columns or rows found in document"],
            )

        _log.info(
            "document_queued_for_ingestion",
            doc_id=doc_content.id,
            filename=filename,
            columns=doc_content.column_names,
            row_count=doc_content.row_count,
        )

        return UploadResult(doc=doc, status="processing")


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
    )
