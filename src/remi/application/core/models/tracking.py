"""Tracking — director follow-up.

ActionItem, Note, MeetingBrief.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from remi.application.core.models._helpers import _utcnow
from remi.application.core.models.enums import (
    ActionItemStatus,
    NoteProvenance,
    Priority,
)


class ActionItem(BaseModel, frozen=True):
    """User-created action item tied to a manager, property, or tenant."""

    id: str
    title: str
    description: str = ""
    status: ActionItemStatus = ActionItemStatus.OPEN
    priority: Priority = Priority.MEDIUM
    manager_id: str | None = None
    property_id: str | None = None
    tenant_id: str | None = None
    due_date: date | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class Note(BaseModel, frozen=True):
    """A note attached to any domain entity.

    Provenance distinguishes user-entered notes from report-derived or
    AI-inferred observations. Notes are first-class domain objects stored
    in the property store and surfaced into the knowledge graph via the bridge.
    """

    id: str
    content: str
    entity_type: str
    entity_id: str
    provenance: NoteProvenance = NoteProvenance.USER_STATED
    source_doc: str | None = None
    created_by: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class MeetingBrief(BaseModel, frozen=True):
    """An LLM-generated meeting review brief for a property manager.

    Each brief is a point-in-time artifact — ``snapshot_hash`` is a
    deterministic hash of the portfolio data that was fed into the pipeline,
    so consumers can tell whether the underlying data has changed since the
    brief was generated.  ``generated_at`` records when.

    ``brief`` and ``analysis`` store the structured JSON output from the
    two pipeline stages.  ``focus`` records the optional user-supplied
    focus area that scoped the generation.
    """

    id: str
    manager_id: str
    snapshot_hash: str
    brief: dict[str, object]
    analysis: dict[str, object]
    focus: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    generated_at: datetime = Field(default_factory=_utcnow)
