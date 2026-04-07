"""Manager resolution during ingestion — find-or-create by tag.

Given a raw manager tag string from a report header (e.g. "Ryan Steen Mgmt"),
resolves it to an existing PropertyManager or creates a new one.  Uses
normalize_entity_name for fuzzy matching against existing managers.

No LLM, no I/O beyond PropertyStore reads/writes.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from remi.application.core.models import PropertyManager
from remi.application.core.protocols import PropertyStore
from remi.application.core.rules import manager_name_from_tag, normalize_entity_name
from remi.types.identity import manager_id as _manager_id

_log = structlog.get_logger(__name__)


@dataclass
class ManagerResolution:
    """Result of resolving a manager tag to a PropertyManager."""

    manager_id: str
    manager_name: str
    created_new: bool = False
    alias_matched: bool = False
    alias_from: str | None = None
    alias_to: str | None = None


class ManagerResolver:
    """Resolves raw manager tags to PropertyManager entities.

    Caches the manager list for the duration of a single document ingestion
    to avoid repeated store queries.
    """

    def __init__(self, property_store: PropertyStore) -> None:
        self._ps = property_store
        self._cache: dict[str, ManagerResolution] | None = None
        self._existing: list[PropertyManager] | None = None

    async def _ensure_loaded(self) -> list[PropertyManager]:
        if self._existing is None:
            self._existing = await self._ps.list_managers()
        return self._existing

    async def ensure_manager(self, tag: str) -> ManagerResolution:
        """Resolve *tag* to an existing or new PropertyManager.

        Resolution strategy:
        1. Exact ID match — tag normalises to the same manager_id as an existing manager.
        2. Fuzzy name match — normalized tag matches normalized existing name.
        3. Create new — no match found, create a new PropertyManager.
        """
        if self._cache and tag in self._cache:
            return self._cache[tag]

        display_name = manager_name_from_tag(tag)
        mid = _manager_id(display_name)
        existing_managers = await self._ensure_loaded()

        # Exact ID match
        for mgr in existing_managers:
            if mgr.id == mid:
                resolution = ManagerResolution(
                    manager_id=mgr.id,
                    manager_name=mgr.name,
                )
                self._set_cache(tag, resolution)
                return resolution

        # Fuzzy name match
        tag_norm = normalize_entity_name(tag)
        for mgr in existing_managers:
            if normalize_entity_name(mgr.name) == tag_norm:
                resolution = ManagerResolution(
                    manager_id=mgr.id,
                    manager_name=mgr.name,
                    alias_matched=True,
                    alias_from=tag,
                    alias_to=mgr.name,
                )
                self._set_cache(tag, resolution)
                return resolution

        # Create new manager
        manager = PropertyManager(
            id=mid,
            name=display_name,
            manager_tag=tag,
        )
        await self._ps.upsert_manager(manager)
        self._existing = None  # invalidate cache

        _log.info(
            "manager_created",
            manager_id=mid,
            manager_name=display_name,
            raw_tag=tag,
        )

        resolution = ManagerResolution(
            manager_id=mid,
            manager_name=display_name,
            created_new=True,
        )
        self._set_cache(tag, resolution)
        return resolution

    def _set_cache(self, tag: str, resolution: ManagerResolution) -> None:
        if self._cache is None:
            self._cache = {}
        self._cache[tag] = resolution
