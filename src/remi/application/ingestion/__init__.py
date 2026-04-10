"""Ingestion — document upload, classification, and entity extraction.

Phase 1 (parse/dedup/save) is handled by ``DocumentIngestService``.
Phase 2 (entity extraction) is handled by the ingester agent using
tools from ``IngestionToolProvider``.

The ``FormatRegistry`` stores confirmed column mappings so repeat
uploads of the same report shape skip the LLM entirely.
"""

from pathlib import Path

from remi.application.ingestion.formats import (
    FormatRegistry,
    InMemoryFormatRegistry,
    IngestionFormat,
    column_signature,
    format_id,
)
from remi.application.ingestion.pipeline import DocumentIngestService
from remi.application.ingestion.tools import IngestionToolProvider

MANIFEST_PATH = Path(__file__).parent / "agents" / "ingester" / "app.yaml"

__all__ = [
    "DocumentIngestService",
    "FormatRegistry",
    "InMemoryFormatRegistry",
    "IngestionFormat",
    "IngestionToolProvider",
    "MANIFEST_PATH",
    "column_signature",
    "format_id",
]
