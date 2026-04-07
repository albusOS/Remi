"""Pydantic output schemas for ingestion workflow LLM steps.

These models validate the structured JSON output from LLM nodes in the
document_ingestion and graph_ingest workflow YAMLs. They're registered
as ``output_schema`` references in the YAML and resolved by the engine
at runtime.

The schemas enforce that the LLM produced usable data before the
pipeline proceeds to mapping and persistence.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# document_ingestion: extract step output
# ---------------------------------------------------------------------------


class ExtractResult(BaseModel):
    """Validated output from the document_ingestion ``extract`` step."""

    report_type: str = "unknown"
    platform: str = "appfolio"
    manager: str | None = None
    scope: str = "unknown"
    effective_date: str | None = None
    date_range_start: str | None = None
    date_range_end: str | None = None
    primary_entity_type: str = ""
    column_map: dict[str, str] = Field(default_factory=dict)
    section_header_column: str | None = None
    observations_likely: bool = False
    unknown_columns: list[str] = Field(default_factory=list)
    needs_inspection: bool = False


# ---------------------------------------------------------------------------
# document_ingestion: inspect step output
# ---------------------------------------------------------------------------


class AmbiguousColumn(BaseModel):
    """A column whose mapping was uncertain and how it was resolved."""

    column: str
    original_mapping: str
    corrected_mapping: str
    reason: str


class InspectResult(BaseModel):
    """Validated output from the document_ingestion ``inspect`` step.

    The inspect step sees real row values and corrects any ambiguous column
    mappings that the extract step got wrong from headers alone.
    """

    column_map: dict[str, str] = Field(default_factory=dict)
    ambiguous_columns: list[AmbiguousColumn] = Field(default_factory=list)
    notes: str = ""


# ---------------------------------------------------------------------------
# document_ingestion: capture step output
# ---------------------------------------------------------------------------


class CapturedEntity(BaseModel):
    entity_type: str
    entity_id: str
    properties: dict[str, object] = Field(default_factory=dict)
    relationships: list[dict[str, str]] = Field(default_factory=list)


class CaptureResult(BaseModel):
    """Validated output from the document_ingestion ``capture`` step."""

    captured: list[CapturedEntity] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# graph_ingest: reason step output
# ---------------------------------------------------------------------------


class GraphOperation(BaseModel):
    """A single graph operation produced by the reasoning step."""

    op: str
    type: str = ""
    id: str = ""
    properties: dict[str, object] = Field(default_factory=dict)
    identity_note: str | None = None
    source_id: str = ""
    target_id: str = ""
    relation: str = ""
    proposed_type: str = ""
    description: str = ""
    fields: list[str] = Field(default_factory=list)
    sample: dict[str, object] = Field(default_factory=dict)
    reason: str = ""
    input_value: str = ""
    candidate_id: str = ""
    confidence: float = 0.0


class GraphReasonResult(BaseModel):
    """Validated output from the graph_ingest ``reason`` step."""

    report_type: str = "unknown"
    platform: str = "appfolio"
    manager: str | None = None
    total_entities: int = 0
    operations: list[GraphOperation] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# graph_ingest: extend step output
# ---------------------------------------------------------------------------


class ProposedField(BaseModel):
    name: str
    type: str = "str"
    required: bool = False
    description: str = ""


class ProposedRelationship(BaseModel):
    relation: str
    target_type: str
    direction: str = "outbound"
    description: str = ""


class ProposedType(BaseModel):
    type_name: str
    description: str = ""
    fields: list[ProposedField] = Field(default_factory=list)
    relationships: list[ProposedRelationship] = Field(default_factory=list)
    reasoning: str = ""


class GraphExtendResult(BaseModel):
    """Validated output from the graph_ingest ``extend`` step."""

    proposed_types: list[ProposedType] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Schema registry — maps YAML output_schema names to Pydantic models
# ---------------------------------------------------------------------------

INGESTION_SCHEMAS: dict[str, type[BaseModel]] = {
    "ExtractResult": ExtractResult,
    "InspectResult": InspectResult,
    "CaptureResult": CaptureResult,
    "GraphReasonResult": GraphReasonResult,
    "GraphExtendResult": GraphExtendResult,
}


# ---------------------------------------------------------------------------
# Pipeline result types (formerly base.py)
# ---------------------------------------------------------------------------

from dataclasses import dataclass, field as dc_field
from enum import StrEnum
from typing import Any as _Any

from remi.application.core.models.enums import ReportType


class ReviewKind(StrEnum):
    AMBIGUOUS_ROW = "ambiguous_row"
    VALIDATION_WARNING = "validation_warning"
    ENTITY_MATCH = "entity_match"
    CLASSIFICATION_UNCERTAIN = "classification_uncertain"
    MANAGER_INFERRED = "manager_inferred"
    OBSERVATION_CAPTURED = "observation_captured"


class ReviewSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ACTION_NEEDED = "action_needed"


@dataclass
class ReviewOption:
    id: str
    label: str


@dataclass
class ReviewItem:
    kind: ReviewKind
    severity: ReviewSeverity
    message: str
    row_index: int | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    field_name: str | None = None
    raw_value: str | None = None
    suggestion: str | None = None
    options: list[ReviewOption] = dc_field(default_factory=list)
    row_data: dict[str, _Any] | None = None


@dataclass
class RowWarning:
    row_index: int
    row_type: str
    field: str
    issue: str
    raw_value: str


@dataclass
class IngestionResult:
    document_id: str
    report_type: ReportType = ReportType.UNKNOWN
    entities_created: int = 0
    relationships_created: int = 0
    rows_accepted: int = 0
    rows_rejected: int = 0
    rows_skipped: int = 0
    observations_captured: int = 0
    validation_warnings: list[RowWarning] = dc_field(default_factory=list)
    persist_errors: list[RowWarning] = dc_field(default_factory=list)
    ambiguous_rows: list[dict[str, _Any]] = dc_field(default_factory=list)
    observation_rows: list[dict[str, _Any]] = dc_field(default_factory=list)
    manager_tags_skipped: list[str] = dc_field(default_factory=list)
    review_items: list[ReviewItem] = dc_field(default_factory=list)


# ---------------------------------------------------------------------------
# API response schemas (formerly document_schemas.py / schemas.py)
# ---------------------------------------------------------------------------


class ReviewOptionSchema(BaseModel):
    id: str
    label: str


class ReviewItemSchema(BaseModel):
    kind: str
    severity: str
    message: str
    row_index: int | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    field_name: str | None = None
    raw_value: str | None = None
    suggestion: str | None = None
    options: list[ReviewOptionSchema] = Field(default_factory=list)
    row_data: dict[str, _Any] | None = None


class KnowledgeInfo(BaseModel):
    entities_extracted: int
    relationships_extracted: int
    ambiguous_rows: int
    rows_accepted: int = 0
    rows_rejected: int = 0
    rows_skipped: int = 0
    observations_captured: int = 0
    validation_warnings: list[str] = Field(default_factory=list)
    review_items: list[ReviewItemSchema] = Field(default_factory=list)


class DuplicateInfo(BaseModel):
    existing_id: str
    existing_filename: str
    uploaded_at: str


class UploadResponse(BaseModel):
    id: str
    filename: str
    content_type: str
    kind: str = "tabular"
    row_count: int
    columns: list[str]
    report_type: str
    chunk_count: int = 0
    page_count: int = 0
    tags: list[str] = Field(default_factory=list)
    size_bytes: int = 0
    knowledge: KnowledgeInfo
    duplicate: DuplicateInfo | None = None


class DocumentListItem(BaseModel):
    id: str
    filename: str
    content_type: str
    kind: str = "tabular"
    row_count: int
    columns: list[str]
    report_type: str
    chunk_count: int = 0
    page_count: int = 0
    tags: list[str] = Field(default_factory=list)
    size_bytes: int = 0
    uploaded_at: str


class DocumentListResponse(BaseModel):
    documents: list[DocumentListItem]


class ChunkItem(BaseModel):
    index: int
    text: str
    page: int | None = None


class DocumentDetail(BaseModel):
    id: str
    filename: str
    content_type: str
    kind: str = "tabular"
    row_count: int
    columns: list[str]
    report_type: str
    chunk_count: int = 0
    page_count: int = 0
    tags: list[str] = Field(default_factory=list)
    size_bytes: int = 0
    preview: list[dict[str, _Any]] = Field(default_factory=list)
    uploaded_at: str


class DocumentRowsResponse(BaseModel):
    document_id: str
    rows: list[dict[str, _Any]]
    count: int


class DocumentChunksResponse(BaseModel):
    document_id: str
    chunks: list[ChunkItem]
    count: int


class TagsResponse(BaseModel):
    tags: list[str]


class TagUpdateRequest(BaseModel):
    tags: list[str]


class CorrectRowRequest(BaseModel):
    row_data: dict[str, _Any]
    report_type: str | None = None


class CorrectRowResponse(BaseModel):
    accepted: bool
    entities_created: int = 0
    relationships_created: int = 0
    review_items: list[ReviewItemSchema] = Field(default_factory=list)
    validation_warnings: list[str] = Field(default_factory=list)


class DeleteResponse(BaseModel):
    deleted: bool
    id: str
