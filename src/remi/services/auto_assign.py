"""AutoAssignService — assign unassigned properties to managers via knowledge graph tags."""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from remi.models.memory import KnowledgeStore
from remi.models.properties import Portfolio, PropertyManager, PropertyStore
from remi.services.snapshots import SnapshotService
from remi.shared.text import manager_name_from_tag, slugify

logger = structlog.get_logger(__name__)


@dataclass
class AutoAssignResult:
    assigned: int
    unresolved: int
    tags_available: int
    message: str


class AutoAssignService:
    def __init__(
        self,
        property_store: PropertyStore,
        knowledge_store: KnowledgeStore,
        snapshot_service: SnapshotService,
    ) -> None:
        self._ps = property_store
        self._ks = knowledge_store
        self._snapshot = snapshot_service

    async def _collect_property_tags(self) -> dict[str, str]:
        """Scan all KB namespaces for appfolio_property entities with a manager_tag."""
        prop_to_tag: dict[str, str] = {}
        namespaces = await self._ks.list_namespaces()
        for ns in namespaces:
            entities = await self._ks.find_entities(
                ns, entity_type="appfolio_property", limit=5000
            )
            for entity in entities:
                tag = entity.properties.get("manager_tag", "")
                if (
                    tag
                    and tag.lower() != "month-to-month"
                    and entity.entity_id not in prop_to_tag
                ):
                    prop_to_tag[entity.entity_id] = tag
        return prop_to_tag

    async def auto_assign(self) -> AutoAssignResult:
        all_props = await self._ps.list_properties()
        unassigned = [p for p in all_props if not p.portfolio_id]

        prop_to_tag = await self._collect_property_tags()

        if not unassigned:
            return AutoAssignResult(
                assigned=0,
                unresolved=0,
                tags_available=len(prop_to_tag),
                message="Nothing to assign",
            )

        portfolio_cache: dict[str, str] = {}

        async def _ensure_manager_cached(tag: str) -> str:
            if tag in portfolio_cache:
                return portfolio_cache[tag]
            mgr_name = manager_name_from_tag(tag)
            manager_id = slugify(f"manager:{mgr_name}")
            await self._ps.upsert_manager(
                PropertyManager(id=manager_id, name=mgr_name, manager_tag=tag)
            )
            portfolio_id = slugify(f"portfolio:{mgr_name}")
            await self._ps.upsert_portfolio(
                Portfolio(
                    id=portfolio_id,
                    manager_id=manager_id,
                    name=f"{mgr_name} Portfolio",
                )
            )
            portfolio_cache[tag] = portfolio_id
            return portfolio_id

        assigned = 0
        unresolved = 0

        for prop in unassigned:
            tag = prop_to_tag.get(prop.id, "")
            if not tag:
                unresolved += 1
                continue
            portfolio_id = await _ensure_manager_cached(tag)
            updated = prop.model_copy(update={"portfolio_id": portfolio_id})
            await self._ps.upsert_property(updated)
            assigned += 1

        try:
            await self._snapshot.capture()
        except Exception:
            logger.warning("snapshot_after_auto_assign_failed", exc_info=True)

        msg = (
            f"Assigned {assigned} properties from knowledge store tags. "
            f"{unresolved} had no tag and remain unassigned."
        )
        return AutoAssignResult(
            assigned=assigned,
            unresolved=unresolved,
            tags_available=len(prop_to_tag),
            message=msg,
        )
