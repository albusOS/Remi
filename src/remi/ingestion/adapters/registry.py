"""Adapter registry — maps raw documents to the right source adapter.

``get_adapter_events`` is the single entry point for the ingestion service.
It tries each known adapter in order and returns the (platform_name, events)
pair from the first one that recognises the document.

To add a new platform:
  1. Create ``adapters/<platform>/`` with its own detector and adapter.
  2. Add a branch in ``get_adapter_events``.
  Nothing else changes.
"""

from __future__ import annotations

from typing import Any

import structlog

from remi.ingestion.events import IngestionEvent
from remi.ingestion.adapters.appfolio.adapter import parse as appfolio_parse
from remi.ingestion.adapters.appfolio.detector import detect_report_type_scored
from remi.ingestion.adapters.appfolio.schema import AppFolioReportType

logger = structlog.get_logger(__name__)


def get_adapter_events(
    doc_id: str,
    column_names: list[str],
    rows: list[dict[str, Any]],
) -> tuple[str, list[IngestionEvent]] | None:
    """Detect the source platform and parse into canonical events.

    Returns ``(platform_name, events)`` when a known adapter claims the
    document, or ``None`` when no adapter matches (caller should fall back to
    LLM classification or generic ingest).
    """
    report_type, _confidence = detect_report_type_scored(column_names)
    if report_type != AppFolioReportType.UNKNOWN:
        events = appfolio_parse(doc_id, column_names, rows)
        if events:
            logger.debug(
                "adapter_matched",
                platform="appfolio",
                doc_id=doc_id,
                report_type=report_type,
                event_count=len(events),
            )
            return ("appfolio", events)

    return None
