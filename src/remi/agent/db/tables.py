"""SQLModel table definitions owned by the agent layer.

Agent-layer row classes live here — one table per agent subsystem that
needs Postgres persistence.  Application-domain tables belong in
``application.infra.stores.pg.tables``, not here.

Naming convention: ``<Entity>Row`` to distinguish from Pydantic DTOs.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlmodel import Field, SQLModel

_TZDateTime = sa.DateTime(timezone=True)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class DocumentRow(SQLModel, table=True):
    __tablename__ = "documents"

    id: str = Field(primary_key=True)
    filename: str
    content_type: str = ""
    uploaded_at: datetime = Field(default_factory=_utcnow, sa_type=_TZDateTime)
    row_count: int = 0
    column_names: list[str] = Field(default_factory=list, sa_type=sa.JSON)
    rows: list[dict[str, Any]] = Field(default_factory=list, sa_type=sa.JSON)
    doc_metadata: dict[str, Any] = Field(default_factory=dict, sa_type=sa.JSON)




# ---------------------------------------------------------------------------
# Vector embeddings table (requires pgvector extension)
# ---------------------------------------------------------------------------


class MemoryEntryRow(SQLModel, table=True):
    __tablename__ = "memory_entries"
    __table_args__ = (sa.Index("ix_memory_ns_key", "namespace", "key"),)

    id: int | None = Field(default=None, primary_key=True)
    namespace: str
    key: str
    value: str = ""
    ttl_seconds: int | None = None
    created_at: datetime = Field(default_factory=_utcnow, sa_type=_TZDateTime)
    updated_at: datetime = Field(default_factory=_utcnow, sa_type=_TZDateTime)


class VectorEmbeddingRow(SQLModel, table=True):
    __tablename__ = "vector_embeddings"
    __table_args__ = (
        sa.Index("ix_vec_source", "source_entity_id"),
        sa.Index("ix_vec_type", "source_entity_type"),
    )

    id: str = Field(primary_key=True)
    text: str = ""
    source_entity_id: str
    source_entity_type: str
    source_field: str = ""
    metadata_: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=sa.JSON,
        sa_column_kwargs={"key": "metadata"},
    )
    created_at: datetime = Field(default_factory=_utcnow, sa_type=_TZDateTime)
    vector: list[float] = Field(default_factory=list, sa_type=sa.JSON)
