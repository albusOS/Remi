"""Intelligence — user-driven fact assertion and entity context annotation."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import structlog

from remi.agent.events import DomainEvent, EventBus
from remi.application.core.events import (
    ChangeEvent,
    ChangeSet,
    ChangeSource,
    ChangeType,
    EventStore,
    FieldChange,
)
from remi.application.core.models import Note
from remi.application.core.protocols import PropertyStore

_log = structlog.get_logger(__name__)


async def assert_fact(
    ps: PropertyStore,
    event_store: EventStore | None,
    event_bus: EventBus | None,
    *,
    entity_type: str,
    entity_id: str | None = None,
    properties: dict[str, str],
    related_to: str | None = None,
    relation_type: str | None = None,
) -> dict[str, str]:
    """Record a new fact by creating a Note with user-level provenance."""
    eid = entity_id or f"{entity_type.lower()}:{uuid4().hex[:12]}"
    note_id = f"assertion:{uuid4().hex[:12]}"
    content_parts = [f"Asserted {entity_type} fact:"]
    for k, v in properties.items():
        content_parts.append(f"  {k}: {v}")
    if related_to and relation_type:
        content_parts.append(f"  Related: {relation_type} -> {related_to}")

    note = Note(
        id=note_id,
        content="\n".join(content_parts),
        entity_type=entity_type,
        entity_id=eid,
        tags=["assertion", "user"],
    )
    await ps.upsert_note(note)

    if event_store is not None:
        now = datetime.now(UTC)
        cs = ChangeSet(
            source=ChangeSource.AGENT_ASSERTION,
            source_detail=f"assert_fact:{entity_type}",
            timestamp=now,
            created=[
                ChangeEvent(
                    entity_type=entity_type,
                    entity_id=eid,
                    change_type=ChangeType.CREATED,
                    fields=tuple(FieldChange(field=k, new_value=v) for k, v in properties.items()),
                    source=ChangeSource.AGENT_ASSERTION,
                    timestamp=now,
                ),
            ],
        )
        await event_store.append(cs)

    if event_bus is not None:
        await event_bus.publish(
            DomainEvent(
                topic="assertion.created",
                source="intelligence.assertions",
                payload={
                    "entity_type": entity_type,
                    "entity_id": eid,
                    "properties": properties,
                },
            )
        )

    _log.info("user_fact_asserted", entity_type=entity_type, entity_id=eid)
    return {"status": "asserted", "entity_id": eid, "entity_type": entity_type}


async def add_context(
    ps: PropertyStore,
    *,
    entity_type: str,
    entity_id: str,
    context: str,
) -> dict[str, str]:
    """Attach a user-context annotation as a Note."""
    note_id = f"context:{uuid4().hex[:12]}"
    note = Note(
        id=note_id,
        content=context,
        entity_type=entity_type,
        entity_id=entity_id,
        tags=["user_context"],
    )
    await ps.upsert_note(note)

    _log.info(
        "user_context_added",
        entity_type=entity_type,
        entity_id=entity_id,
        note_id=note_id,
    )
    return {"status": "context_added", "note_id": note_id, "entity_id": entity_id}
