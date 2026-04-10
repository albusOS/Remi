"""Ingestion models — pipeline results and API response types."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field
from enum import StrEnum
from typing import Any as _Any

from pydantic import BaseModel, Field

from remi.application.core.models.enums import ReportType

# ---------------------------------------------------------------------------
# Pipeline result types
# ---------------------------------------------------------------------------


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
    status: str = "complete"
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
