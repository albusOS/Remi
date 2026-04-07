"""Ingestion workflow tools on the shared ``ToolRegistry``.

``register_ingestion_tools`` binds per-upload state (``ctx``, ``result``,
``all_rows``) and registers ``apply_column_map``, ``validate_rows``, and
``persist_row`` so the workflow engine can resolve transform/for_each steps
from the registry. Call it immediately before ``WorkflowRunner.run`` for
each document; re-registration overwrites the same tool names for the next
upload.
"""

from __future__ import annotations

from typing import Any

import structlog

from remi.agent.llm.types import ToolDefinition
from remi.agent.types import ToolRegistry
from remi.application.services.ingestion.base import IngestionResult, RowWarning
from remi.application.services.ingestion.context import IngestionCtx
from remi.application.services.ingestion.mapper import apply_column_map
from remi.application.services.ingestion.persisters import ROW_PERSISTERS
from remi.application.services.ingestion.validation import validate_rows

_log = structlog.get_logger(__name__)


def register_ingestion_tools(
    registry: ToolRegistry,
    ctx: IngestionCtx,
    result: IngestionResult,
    all_rows: list[dict[str, Any]],
) -> None:
    """Register ingestion transform tools, closed over this upload's state."""

    async def _apply_column_map_tool(args: dict[str, Any]) -> dict[str, Any]:
        column_map: dict[str, str] = args.get("column_map", {})
        entity_type: str = args.get("entity_type", "")
        section_header: str | None = args.get("section_header_column")

        if not column_map or not entity_type:
            return {"rows": [], "skipped": 0}

        mapped = apply_column_map(
            all_rows,
            column_map,
            entity_type,
            section_header_column=section_header,
        )
        return {"rows": mapped, "total": len(all_rows), "mapped": len(mapped)}

    async def _validate_rows_tool(args: dict[str, Any]) -> dict[str, Any]:
        rows = args.get("rows", [])
        if not isinstance(rows, list):
            rows = []

        accepted = validate_rows(rows, result)
        return {
            "accepted": accepted,
            "total": len(rows),
            "accepted_count": len(accepted),
            "rejected_count": result.rows_rejected,
        }

    async def _persist_row_tool(args: dict[str, Any]) -> dict[str, str]:
        entity_type = args.get("type", "")
        persister = ROW_PERSISTERS.get(entity_type)

        if persister is None:
            result.observation_rows.append(args)
            result.rows_skipped += 1
            return {"status": "skipped", "type": entity_type}

        try:
            await persister(args, ctx)
            return {"status": "ok", "type": entity_type}
        except Exception as exc:
            _log.warning(
                "row_persist_error",
                entity_type=entity_type,
                error=str(exc),
                exc_info=True,
            )
            result.persist_errors.append(
                RowWarning(
                    row_index=0,
                    row_type=entity_type,
                    field="",
                    issue="persistence failed",
                    raw_value=str(args)[:200],
                )
            )
            result.rows_rejected += 1
            raise

    registry.register(
        "apply_column_map",
        _apply_column_map_tool,
        ToolDefinition(
            name="apply_column_map",
            description="Map document columns to entity fields",
        ),
    )
    registry.register(
        "validate_rows",
        _validate_rows_tool,
        ToolDefinition(
            name="validate_rows",
            description="Validate mapped rows for ingestion",
        ),
    )
    registry.register(
        "persist_row",
        _persist_row_tool,
        ToolDefinition(
            name="persist_row",
            description="Persist a single validated row",
        ),
    )
