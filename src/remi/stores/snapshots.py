"""Snapshot storage — durable append-only JSONL persistence.

Layer 1 (Facts): storage adapter only, no business logic.

``JsonLinesSnapshotStore`` appends every snapshot batch to a JSONL file on
disk and loads all history into memory on startup for fast queries.
Each line is a JSON-serialized snapshot dict with a ``_type`` discriminator
("manager" or "property") so both ``ManagerSnapshot`` and ``PropertySnapshot``
can coexist in the same file.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

import structlog

logger = structlog.get_logger("remi.stores.snapshots")


@runtime_checkable
class SnapshotStore(Protocol):
    """Port for snapshot persistence."""

    def append_manager_snapshots(self, snapshots: list[dict]) -> None: ...
    def append_property_snapshots(self, snapshots: list[dict]) -> None: ...

    def list_manager_snapshots(
        self,
        manager_id: str | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[dict]: ...

    def list_property_snapshots(
        self,
        property_id: str | None = None,
        manager_id: str | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[dict]: ...

    def latest_manager_snapshot(self, manager_id: str) -> dict | None: ...
    def previous_manager_snapshot(self, manager_id: str) -> dict | None: ...


class InMemorySnapshotStore:
    """Non-durable in-memory snapshot store (default when no path configured)."""

    def __init__(self) -> None:
        self._manager: list[dict] = []
        self._property: list[dict] = []

    def append_manager_snapshots(self, snapshots: list[dict]) -> None:
        self._manager.extend(snapshots)

    def append_property_snapshots(self, snapshots: list[dict]) -> None:
        self._property.extend(snapshots)

    def list_manager_snapshots(
        self,
        manager_id: str | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        rows = self._manager
        if manager_id:
            rows = [r for r in rows if r.get("manager_id") == manager_id]
        if since:
            rows = [r for r in rows if _parse_ts(r.get("timestamp")) >= since]
        if limit:
            rows = rows[-limit:]
        return list(rows)

    def list_property_snapshots(
        self,
        property_id: str | None = None,
        manager_id: str | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        rows = self._property
        if property_id:
            rows = [r for r in rows if r.get("property_id") == property_id]
        if manager_id:
            rows = [r for r in rows if r.get("manager_id") == manager_id]
        if since:
            rows = [r for r in rows if _parse_ts(r.get("timestamp")) >= since]
        if limit:
            rows = rows[-limit:]
        return list(rows)

    def latest_manager_snapshot(self, manager_id: str) -> dict | None:
        matching = [r for r in self._manager if r.get("manager_id") == manager_id]
        return matching[-1] if matching else None

    def previous_manager_snapshot(self, manager_id: str) -> dict | None:
        matching = [r for r in self._manager if r.get("manager_id") == manager_id]
        return matching[-2] if len(matching) >= 2 else None


class JsonLinesSnapshotStore:
    """Durable append-only JSONL snapshot store.

    All snapshots are written to ``path`` as newline-delimited JSON.
    Each record includes a ``_type`` field ("manager" or "property") for
    discrimination on load. The in-memory lists are built from the file at
    startup and kept in sync as new snapshots arrive.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._manager: list[dict] = []
        self._property: list[dict] = []
        self._load()

    # ------------------------------------------------------------------
    # Startup load
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            return
        loaded = 0
        errors = 0
        with self._path.open(encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    rtype = record.get("_type")
                    if rtype == "manager":
                        self._manager.append(record)
                    elif rtype == "property":
                        self._property.append(record)
                    loaded += 1
                except json.JSONDecodeError:
                    errors += 1
                    logger.warning("snapshot_line_invalid", path=str(self._path), lineno=lineno)
        logger.info(
            "snapshots_loaded",
            path=str(self._path),
            manager_count=len(self._manager),
            property_count=len(self._property),
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def _append_lines(self, records: list[dict]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as fh:
            for record in records:
                fh.write(json.dumps(record, default=str) + "\n")

    def append_manager_snapshots(self, snapshots: list[dict]) -> None:
        tagged = [{**s, "_type": "manager"} for s in snapshots]
        self._append_lines(tagged)
        self._manager.extend(tagged)

    def append_property_snapshots(self, snapshots: list[dict]) -> None:
        tagged = [{**s, "_type": "property"} for s in snapshots]
        self._append_lines(tagged)
        self._property.extend(tagged)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def list_manager_snapshots(
        self,
        manager_id: str | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        rows = self._manager
        if manager_id:
            rows = [r for r in rows if r.get("manager_id") == manager_id]
        if since:
            rows = [r for r in rows if _parse_ts(r.get("timestamp")) >= since]
        if limit:
            rows = rows[-limit:]
        return list(rows)

    def list_property_snapshots(
        self,
        property_id: str | None = None,
        manager_id: str | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        rows = self._property
        if property_id:
            rows = [r for r in rows if r.get("property_id") == property_id]
        if manager_id:
            rows = [r for r in rows if r.get("manager_id") == manager_id]
        if since:
            rows = [r for r in rows if _parse_ts(r.get("timestamp")) >= since]
        if limit:
            rows = rows[-limit:]
        return list(rows)

    def latest_manager_snapshot(self, manager_id: str) -> dict | None:
        matching = [r for r in self._manager if r.get("manager_id") == manager_id]
        return matching[-1] if matching else None

    def previous_manager_snapshot(self, manager_id: str) -> dict | None:
        matching = [r for r in self._manager if r.get("manager_id") == manager_id]
        return matching[-2] if len(matching) >= 2 else None


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _parse_ts(value: str | None) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=UTC)
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except ValueError:
        return datetime.min.replace(tzinfo=UTC)
