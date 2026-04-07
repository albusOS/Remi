"""AutoAssignService — tag-based property-to-manager assignment."""

from __future__ import annotations

import structlog

from remi.application.core.protocols import PropertyStore
from remi.application.core.rules import manager_name_from_tag
from remi.application.views import AutoAssignResult
from remi.types.identity import manager_id as _manager_id

logger = structlog.get_logger(__name__)


class AutoAssignService:
    def __init__(
        self,
        property_store: PropertyStore,
    ) -> None:
        self._ps = property_store

    async def _collect_property_tags(self) -> dict[str, str]:
        """Build property_id -> manager_tag from Property.manager_tag field."""
        props = await self._ps.list_properties()
        return {
            p.id: p.manager_tag
            for p in props
            if p.manager_tag and p.manager_tag.lower() != "month-to-month"
        }

    async def _build_tag_to_manager(self) -> dict[str, str]:
        """Map manager tags/names to manager_id."""
        managers = await self._ps.list_managers()

        tag_map: dict[str, str] = {}
        for m in managers:
            if m.manager_tag:
                tag_map[m.manager_tag] = m.id
            tag_map[m.name] = m.id
            mgr_name = manager_name_from_tag(m.manager_tag or m.name)
            tag_map[mgr_name] = m.id

        return tag_map

    async def auto_assign(self) -> AutoAssignResult:
        all_props = await self._ps.list_properties()
        unassigned = [p for p in all_props if not p.manager_id]

        prop_to_tag = await self._collect_property_tags()

        if not unassigned:
            return AutoAssignResult(
                assigned=0,
                unresolved=0,
                tags_available=len(prop_to_tag),
                message="Nothing to assign",
            )

        tag_map = await self._build_tag_to_manager()

        assigned = 0
        unresolved = 0

        for prop in unassigned:
            tag = prop_to_tag.get(prop.id, "")
            if not tag:
                unresolved += 1
                continue

            mgr_id = tag_map.get(tag)
            if not mgr_id:
                mgr_name = manager_name_from_tag(tag)
                mgr_id = tag_map.get(mgr_name)

            if not mgr_id:
                slug = _manager_id(manager_name_from_tag(tag))
                for key, mid in tag_map.items():
                    if _manager_id(manager_name_from_tag(key)) == slug:
                        mgr_id = mid
                        break

            if not mgr_id:
                unresolved += 1
                continue

            updated = prop.model_copy(update={"manager_id": mgr_id})
            await self._ps.upsert_property(updated)
            assigned += 1

        msg = (
            f"Assigned {assigned} properties to existing managers. "
            f"{unresolved} had no tag or no matching manager."
        )
        return AutoAssignResult(
            assigned=assigned,
            unresolved=unresolved,
            tags_available=len(prop_to_tag),
            message=msg,
        )
