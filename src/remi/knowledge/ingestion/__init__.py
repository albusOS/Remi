"""knowledge.ingestion — schema-driven entity extraction from documents.

Submodules:
  base      — IngestionResult (shared result type)
  service   — IngestionService (orchestrator)
  schema    — ReportSchema definitions and unified ingest_report() loop
  managers  — Manager resolution with frequency-based classification
  generic   — fallback for unrecognized report types
  helpers   — parse_address, occupancy_to_unit_status, entity_id_from_row
"""

from remi.knowledge.ingestion.base import IngestionResult
from remi.knowledge.ingestion.service import IngestionService

__all__ = ["IngestionResult", "IngestionService"]
