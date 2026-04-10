"""Ingestion — document upload, classification, and entity extraction.

Phase 1 (parse/dedup/save) is handled by ``DocumentIngestService``.
Phase 2 (entity extraction) runs a deterministic pipeline: column
vocabulary matching (``vocab.py``) handles all known AppFolio formats
instantly. The LLM fallback only fires for genuinely unrecognised
column sets.

The ``FormatRegistry`` stores LLM-confirmed column mappings so those
formats also become instant on repeat uploads.
"""

from pathlib import Path

from remi.application.ingestion.formats import (
    FormatRegistry,
    IngestionFormat,
    InMemoryFormatRegistry,
    column_signature,
    format_id,
)
from remi.application.ingestion.rules import ReportDates, resolve_report_dates
from remi.application.ingestion.tools import IngestionToolProvider
from remi.application.ingestion.upload import DocumentIngestService
from remi.application.ingestion.vocab import VocabMatch, match_columns

MANIFEST_PATH = Path(__file__).resolve().parent.parent / "agents" / "ingester" / "app.yaml"

__all__ = [
    "DocumentIngestService",
    "FormatRegistry",
    "InMemoryFormatRegistry",
    "IngestionFormat",
    "IngestionToolProvider",
    "MANIFEST_PATH",
    "ReportDates",
    "VocabMatch",
    "column_signature",
    "format_id",
    "match_columns",
    "resolve_report_dates",
]
