"""IngestionFormat registry — learned column mappings that grow with use.

Once a human confirms a column mapping for a particular (manager, report_type,
column_signature) triple, every subsequent upload of the same format is instant,
LLM-free, and correct.

The registry is an in-process store (protocol-first, swappable for Postgres).
It is queried **before** the LLM sees the document — an exact match means zero
AI involvement.  A miss means the agent builds a proposed mapping which, after
human confirmation, is saved here for next time.
"""

from __future__ import annotations

import abc
import hashlib
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class IngestionFormat(BaseModel, frozen=True):
    """A confirmed column mapping for a specific report shape.

    The ``column_signature`` is a stable hash of the sorted, lowercased
    column headers — it identifies the *shape* of the report regardless
    of row content.
    """

    id: str
    manager_id: str
    report_type: str
    column_signature: str
    column_map: dict[str, str]
    primary_entity_type: str
    scope: str = "unknown"
    platform: str = "appfolio"
    confirmed_by_human: bool = False
    use_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_used: datetime = Field(default_factory=lambda: datetime.now(UTC))


def column_signature(columns: list[str]) -> str:
    """Compute a stable hash from column headers.

    The signature is order-independent (sorted) and case-insensitive
    so minor reorderings or casing changes still match.
    """
    normalized = sorted(c.strip().lower() for c in columns if c.strip())
    raw = "|".join(normalized)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def format_id(manager_id: str, report_type: str, col_sig: str) -> str:
    """Deterministic ID for a format record."""
    raw = f"{manager_id}:{report_type}:{col_sig}"
    return f"fmt-{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


class FormatRegistry(abc.ABC):
    """Port for storing and retrieving confirmed ingestion formats."""

    @abc.abstractmethod
    async def lookup(
        self,
        *,
        manager_id: str,
        report_type: str,
        col_sig: str,
    ) -> IngestionFormat | None:
        """Find an exact match by (manager_id, report_type, column_signature)."""

    @abc.abstractmethod
    async def lookup_by_signature(self, col_sig: str) -> list[IngestionFormat]:
        """Find all formats matching a column signature (any manager/type)."""

    @abc.abstractmethod
    async def save(self, fmt: IngestionFormat) -> IngestionFormat:
        """Create or update a format record. Returns the saved version."""

    @abc.abstractmethod
    async def record_use(self, format_id: str) -> None:
        """Increment use_count and update last_used timestamp."""

    @abc.abstractmethod
    async def list_all(
        self,
        *,
        manager_id: str | None = None,
        confirmed_only: bool = False,
    ) -> list[IngestionFormat]:
        """List formats, optionally filtered."""


class InMemoryFormatRegistry(FormatRegistry):
    """In-memory format registry for development and testing."""

    def __init__(self) -> None:
        self._by_id: dict[str, IngestionFormat] = {}
        self._by_key: dict[tuple[str, str, str], str] = {}

    async def lookup(
        self,
        *,
        manager_id: str,
        report_type: str,
        col_sig: str,
    ) -> IngestionFormat | None:
        fid = self._by_key.get((manager_id, report_type, col_sig))
        if fid is None:
            return None
        return self._by_id.get(fid)

    async def lookup_by_signature(self, col_sig: str) -> list[IngestionFormat]:
        return [
            f for f in self._by_id.values()
            if f.column_signature == col_sig
        ]

    async def save(self, fmt: IngestionFormat) -> IngestionFormat:
        self._by_id[fmt.id] = fmt
        self._by_key[(fmt.manager_id, fmt.report_type, fmt.column_signature)] = fmt.id
        return fmt

    async def record_use(self, fid: str) -> None:
        existing = self._by_id.get(fid)
        if existing is None:
            return
        updated = existing.model_copy(
            update={
                "use_count": existing.use_count + 1,
                "last_used": datetime.now(UTC),
            }
        )
        self._by_id[fid] = updated

    async def list_all(
        self,
        *,
        manager_id: str | None = None,
        confirmed_only: bool = False,
    ) -> list[IngestionFormat]:
        items = list(self._by_id.values())
        if manager_id:
            items = [f for f in items if f.manager_id == manager_id]
        if confirmed_only:
            items = [f for f in items if f.confirmed_by_human]
        return items
