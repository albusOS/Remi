"""Ingestion service — row-level persistence via IngestionCtx + ROW_PERSISTERS.

Takes already-classified, mapped, and validated rows and runs them through
the per-entity-type persisters. This is the pure persistence tier: no
parsing, no classification, no LLM calls.

Called by ``DocumentIngestService`` (pipeline.py) after the classify + map +
validate phases are complete.
"""

from __future__ import annotations

from typing import Any

import structlog

from remi.agent.documents.types import DocumentContent
from remi.agent.workflow import WorkflowRunner
from remi.application.core.models.enums import ReportType
from remi.application.core.protocols import PropertyStore
from remi.application.services.ingestion.base import IngestionResult
from remi.application.services.ingestion.context import IngestionCtx
from remi.application.services.ingestion.managers import ManagerResolver
from remi.application.services.ingestion.persisters import ROW_PERSISTERS
from remi.types.identity import manager_id as _manager_id

_log = structlog.get_logger(__name__)


class IngestionService:
    """Persists mapped rows via ROW_PERSISTERS, accumulating results.

    Holds references to PropertyStore for building the IngestionCtx.
    The workflow_runner is used by the orchestrator (pipeline.py)
    for LLM extraction.
    """

    def __init__(
        self,
        property_store: PropertyStore,
        workflow_runner: WorkflowRunner,
    ) -> None:
        self._ps = property_store
        self._workflow_runner = workflow_runner

    async def ingest_mapped_rows(
        self,
        content: DocumentContent,
        *,
        report_type: ReportType,
        rows: list[dict[str, Any]],
        manager: str | None = None,
    ) -> IngestionResult:
        """Persist a list of mapped, validated rows."""
        result = IngestionResult(document_id=content.id, report_type=report_type)
        resolver = ManagerResolver(self._ps)

        upload_manager_id: str | None = None
        if manager:
            from remi.application.core.rules import manager_name_from_tag

            display_name = manager_name_from_tag(manager)
            upload_manager_id = _manager_id(display_name)

        ctx = IngestionCtx(
            platform=content.metadata.get("platform", "appfolio"),
            report_type=report_type,
            doc_id=content.id,
            namespace="ingestion",
            ps=self._ps,
            manager_resolver=resolver,
            result=result,
            upload_manager_id=upload_manager_id,
        )

        for idx, row in enumerate(rows):
            entity_type = row.get("type", "")
            persister = ROW_PERSISTERS.get(entity_type)

            if persister is None:
                result.observation_rows.append(row)
                result.rows_skipped += 1
                _log.info(
                    "row_no_persister",
                    row_index=idx,
                    entity_type=entity_type,
                )
                continue

            try:
                await persister(row, ctx)
            except Exception:
                _log.warning(
                    "row_persist_error",
                    row_index=idx,
                    entity_type=entity_type,
                    exc_info=True,
                )
                from remi.application.services.ingestion.base import RowWarning

                result.persist_errors.append(
                    RowWarning(
                        row_index=idx,
                        row_type=entity_type,
                        field="",
                        issue="persistence failed",
                        raw_value=str(row),
                    )
                )
                result.rows_rejected += 1

        _log.info(
            "ingestion_complete",
            doc_id=content.id,
            report_type=report_type.value,
            entities_created=result.entities_created,
            rows_accepted=result.rows_accepted,
            rows_rejected=result.rows_rejected,
            rows_skipped=result.rows_skipped,
        )

        return result
