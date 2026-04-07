"""Tests for ChangeEvent / ChangeSet types and InMemoryEventStore."""

from __future__ import annotations

import pytest

from remi.application.core.events import (
    ChangeEvent,
    ChangeSet,
    ChangeSource,
    ChangeType,
    FieldChange,
)
from remi.application.stores.events import InMemoryEventStore


def _balance_event(entity_id: str = "tenant-carlos") -> ChangeEvent:
    return ChangeEvent(
        entity_type="Tenant",
        entity_id=entity_id,
        change_type=ChangeType.UPDATED,
        fields=(FieldChange(field="balance_owed", old_value=500.0, new_value=700.0),),
        source=ChangeSource.ADAPTER_IMPORT,
    )


def test_changeset_summary() -> None:
    cs = ChangeSet()
    cs.created.append(
        ChangeEvent(
            entity_type="Unit",
            entity_id="unit-new",
            change_type=ChangeType.CREATED,
        )
    )
    cs.updated.append(_balance_event())
    cs.unchanged_ids.append("unit-existing")

    assert cs.total_changes == 2
    assert not cs.is_empty
    assert cs.summary() == {
        "created": 1,
        "updated": 1,
        "unchanged": 1,
        "removed": 0,
    }


def test_empty_changeset() -> None:
    cs = ChangeSet()
    cs.unchanged_ids.append("unit-1")
    assert cs.is_empty
    assert cs.total_changes == 0


def test_events_aggregates_all_changes() -> None:
    cs = ChangeSet()
    created = ChangeEvent(
        entity_type="Unit",
        entity_id="u1",
        change_type=ChangeType.CREATED,
    )
    updated = _balance_event()
    removed = ChangeEvent(
        entity_type="Lease",
        entity_id="l1",
        change_type=ChangeType.REMOVED,
    )
    cs.created.append(created)
    cs.updated.append(updated)
    cs.removed.append(removed)

    assert cs.events == [created, updated, removed]


@pytest.mark.asyncio
async def test_event_store_append_and_get() -> None:
    store = InMemoryEventStore()
    cs = ChangeSet(id="cs-test")
    cs.created.append(
        ChangeEvent(
            entity_type="Unit",
            entity_id="u1",
            change_type=ChangeType.CREATED,
        )
    )
    await store.append(cs)

    retrieved = await store.get("cs-test")
    assert retrieved is cs


@pytest.mark.asyncio
async def test_event_store_list_by_entity() -> None:
    store = InMemoryEventStore()

    cs1 = ChangeSet(id="cs-1")
    cs1.updated.append(_balance_event("tenant-carlos"))
    await store.append(cs1)

    cs2 = ChangeSet(id="cs-2")
    cs2.created.append(
        ChangeEvent(
            entity_type="Unit",
            entity_id="unit-other",
            change_type=ChangeType.CREATED,
        )
    )
    await store.append(cs2)

    carlos_history = await store.list_by_entity("tenant-carlos")
    assert len(carlos_history) == 1
    assert carlos_history[0].id == "cs-1"


@pytest.mark.asyncio
async def test_event_store_list_recent() -> None:
    store = InMemoryEventStore()

    for i in range(5):
        cs = ChangeSet(id=f"cs-{i}")
        cs.unchanged_ids.append(f"entity-{i}")
        await store.append(cs)

    recent = await store.list_recent(limit=3)
    assert len(recent) == 3
    assert recent[0].id == "cs-4"
    assert recent[2].id == "cs-2"
