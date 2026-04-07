"""Document ingestion orchestrator — workflow-driven upload pipeline.

Guards (parse, dedup, non-tabular, empty) stay as Python because they
decide whether to invoke the workflow at all. The full tabular pipeline
(extract → map → validate → persist) runs as a YAML workflow with typed
Pydantic nodes, retry policies, and for-each persistence.

Phases:
  1. Parse     — file bytes to ``DocumentContent``
  2. Dedup     — content-hash duplicate check
  3. Guard     — non-tabular / empty early exits
  4. Workflow  — document_ingestion workflow (extract, map, validate, persist)
  5. Manager   — ensure PropertyManager from user-supplied param
  6. Store     — save to ContentStore + PropertyStore
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

import structlog

from remi.agent.documents import ContentStore
from remi.agent.documents.parsers import parse_document
from remi.agent.documents.types import DocumentKind
from remi.agent.workflow import load_workflow
from remi.application.core.models import (
    Document,
    DocumentType,
    PropertyManager,
    ReportType,
)
from remi.application.services.ingestion.matcher import entity_schemas_for_prompt
from remi.application.services.ingestion.base import (
    IngestionResult,
    ReviewItem,
    RowWarning,
)
from remi.application.services.ingestion.schemas import INGESTION_SCHEMAS
from remi.application.services.ingestion.service import IngestionService
from remi.application.services.ingestion.transforms import register_ingestion_tools
from remi.types.identity import manager_id as _manager_id

_log = structlog.get_logger(__name__)


@dataclass
class UploadResult:
    """Result of the full upload pipeline, consumed by the API and tool layers."""

    doc: Document
    report_type: str = "unknown"
    entities_extracted: int = 0
    relationships_extracted: int = 0
    ambiguous_rows: int = 0
    rows_accepted: int = 0
    rows_rejected: int = 0
    rows_skipped: int = 0
    observations_captured: int = 0
    validation_warnings: list[RowWarning] = field(default_factory=list)
    review_items: list[ReviewItem] = field(default_factory=list)
    pipeline_warnings: list[str] = field(default_factory=list)
    duplicate_of: Document | None = None


class DocumentIngestService:
    """Top-level orchestrator for document uploads.

    ``_ingestion`` is exposed for the ``correct_row`` API endpoint.
    """

    def __init__(
        self,
        content_store: ContentStore,
        ingestion_service: IngestionService,
        metadata_skip_patterns: tuple[str, ...] = (),
        section_labels: frozenset[str] = frozenset(),
    ) -> None:
        self._content_store = content_store
        self._ingestion = ingestion_service
        self._skip_patterns = metadata_skip_patterns
        self._section_labels = section_labels

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
        """Run the full ingestion workflow."""

        # -- Phase 1: Parse -------------------------------------------------------
        doc_content = parse_document(
            filename,
            content,
            content_type,
            extra_skip_patterns=self._skip_patterns,
            section_labels=self._section_labels,
        )
        doc_content.size_bytes = len(content)

        # -- Phase 2: Dedup -------------------------------------------------------
        content_hash = hashlib.sha256(content).hexdigest()

        existing_doc = await self._ingestion._ps.find_by_content_hash(content_hash)
        if existing_doc is not None:
            doc_model = _build_document_model(
                doc_content, content_hash=content_hash,
                document_type=document_type, unit_id=unit_id,
                property_id=property_id, lease_id=lease_id,
            )
            return UploadResult(
                doc=doc_model,
                duplicate_of=existing_doc,
                report_type=existing_doc.report_type.value,
            )

        # -- Phase 3: Non-tabular guard -------------------------------------------
        if doc_content.kind != DocumentKind.tabular:
            await self._content_store.save(doc_content)
            doc_model = _build_document_model(
                doc_content, content_hash=content_hash,
                document_type=document_type, unit_id=unit_id,
                property_id=property_id, lease_id=lease_id,
            )
            await self._ingestion._ps.upsert_document(doc_model)
            return UploadResult(doc=doc_model, report_type="unknown")

        columns = doc_content.column_names
        rows = doc_content.rows
        warnings: list[str] = []

        if not columns or not rows:
            warnings.append("No columns or rows found in document")
            await self._content_store.save(doc_content)
            doc_model = _build_document_model(
                doc_content, content_hash=content_hash,
                document_type=document_type, unit_id=unit_id,
                property_id=property_id, lease_id=lease_id,
            )
            await self._ingestion._ps.upsert_document(doc_model)
            return UploadResult(doc=doc_model, pipeline_warnings=warnings)

        # -- Phase 4: Workflow (extract → map → validate → persist) ---------------
        result, extract_data = await self._run_ingestion_workflow(
            doc_content, rows, manager=manager,
        )

        report_type_str = extract_data.get("report_type", "unknown")
        llm_manager = extract_data.get("manager")
        rt = _resolve_report_type(report_type_str)

        # -- Phase 5: Manager ensure ----------------------------------------------
        effective_manager_id: str | None = None
        if manager:
            effective_manager_id = await self._ensure_manager(manager)

        # -- Phase 6: Store -------------------------------------------------------
        await self._content_store.save(doc_content)
        doc_model = _build_document_model(
            doc_content, content_hash=content_hash, report_type=rt,
            document_type=document_type, unit_id=unit_id,
            property_id=property_id, lease_id=lease_id,
            manager_id=effective_manager_id, report_manager=llm_manager,
        )
        await self._ingestion._ps.upsert_document(doc_model)

        return UploadResult(
            doc=doc_model,
            report_type=rt.value,
            entities_extracted=result.entities_created,
            relationships_extracted=result.relationships_created,
            ambiguous_rows=len(result.ambiguous_rows),
            rows_accepted=result.rows_accepted,
            rows_rejected=result.rows_rejected,
            rows_skipped=result.rows_skipped,
            observations_captured=result.observations_captured,
            validation_warnings=result.validation_warnings,
            review_items=result.review_items,
            pipeline_warnings=warnings,
        )

    async def _run_ingestion_workflow(
        self,
        content: Any,
        rows: list[dict[str, Any]],
        *,
        manager: str | None = None,
    ) -> tuple[IngestionResult, dict[str, Any]]:
        """Execute the document_ingestion workflow and return results."""
        from remi.application.core.models.enums import ReportType as _RT
        from remi.application.services.ingestion.context import IngestionCtx
        from remi.application.services.ingestion.managers import ManagerResolver

        result = IngestionResult(document_id=content.id, report_type=_RT.UNKNOWN)
        resolver = ManagerResolver(self._ingestion._ps)

        upload_manager_id: str | None = None
        if manager:
            from remi.application.core.rules import manager_name_from_tag
            display_name = manager_name_from_tag(manager)
            upload_manager_id = _manager_id(display_name)

        ctx = IngestionCtx(
            platform=content.metadata.get("platform", "appfolio"),
            report_type=_RT.UNKNOWN,
            doc_id=content.id,
            namespace="ingestion",
            kb=self._ingestion._kb,
            ps=self._ingestion._ps,
            manager_resolver=resolver,
            result=result,
            upload_manager_id=upload_manager_id,
        )

        register_ingestion_tools(
            self._ingestion._workflow_runner._tool_registry, ctx, result, rows
        )

        workflow_input = json.dumps(
            {
                "metadata": content.metadata or {},
                "column_names": content.column_names,
                "sample_rows": content.rows[:5],
            },
            default=str,
        )
        context = {"entity_schemas": entity_schemas_for_prompt()}

        try:
            workflow_def = load_workflow("document_ingestion")
            wf_result = await self._ingestion._workflow_runner.run(
                workflow_def,
                workflow_input,
                context=context,
                output_schemas=INGESTION_SCHEMAS,
            )
        except Exception:
            _log.warning("ingestion_workflow_failed", exc_info=True)
            return result, {}

        extract_value = wf_result.step("extract")
        extract_data = extract_value if isinstance(extract_value, dict) else {}

        rt_str = extract_data.get("report_type", "unknown")
        try:
            result.report_type = _RT(rt_str)
        except ValueError:
            result.report_type = _RT.UNKNOWN

        return result, extract_data

    async def _ensure_manager(self, manager_name: str) -> str:
        """Create the PropertyManager entity if it doesn't already exist."""
        from remi.application.core.rules import manager_name_from_tag

        display_name = manager_name_from_tag(manager_name)
        mid = _manager_id(display_name)

        existing = await self._ingestion._ps.get_manager(mid)
        if existing is None:
            mgr = PropertyManager(id=mid, name=display_name)
            await self._ingestion._ps.upsert_manager(mgr)
            _log.info("manager_auto_created", manager_id=mid, name=display_name)

        return mid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_report_type(raw: str) -> ReportType:
    try:
        return ReportType(raw)
    except ValueError:
        return ReportType.UNKNOWN


def _build_document_model(
    content: Any,
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
