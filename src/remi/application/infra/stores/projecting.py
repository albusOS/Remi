"""ProjectingPropertyStore — decorator that auto-projects FK edges after each upsert.

Wraps any PropertyStore and calls GraphProjector.project_entity after every
successful upsert, keeping the knowledge graph live without coupling the
store implementations to the graph layer.

Reads, lists, deletes, and non-projecting writes resolve on the inner store via
``__getattr__`` delegation. Only upsert paths that materialize graph edges are
overridden explicitly.

This wrapper does not subclass ``PropertyStore``: abstract method stubs on the
ABC would be found before ``__getattr__`` and would not forward to the inner
store. ``PropertyStore.register`` provides virtual subclassing for
``isinstance`` / ``issubclass``.
"""

from __future__ import annotations

from typing import cast

import structlog

from remi.agent.graph import GraphProjector
from remi.application.core.models import (
    ActionItem,
    Document,
    Lease,
    MaintenanceRequest,
    Note,
    Owner,
    Property,
    PropertyManager,
    Tenant,
    Unit,
    Vendor,
)
from remi.application.core.protocols import PropertyStore
from remi.types.result import WriteOutcome, WriteResult

_log = structlog.get_logger(__name__)


class ProjectingPropertyStore:
    """Wraps a PropertyStore and projects FK edges into the knowledge graph after upserts."""

    def __init__(self, inner: PropertyStore, projector: GraphProjector) -> None:
        self._inner = inner
        self._projector = projector

    async def _project(self, entity_type: str, entity_id: str, data: dict[str, object]) -> None:
        try:
            await self._projector.project_entity(entity_type, entity_id, data)
        except Exception:
            _log.warning(
                "auto_projection_failed",
                entity_type=entity_type,
                entity_id=entity_id,
                exc_info=True,
            )

    def __getattr__(self, name: str) -> object:
        return getattr(self._inner, name)

    async def upsert_manager(self, manager: PropertyManager) -> WriteResult[PropertyManager]:
        result = await self._inner.upsert_manager(manager)
        if result.outcome != WriteOutcome.NOOP:
            await self._project("PropertyManager", manager.id, manager.model_dump(mode="json"))
        return result

    async def upsert_property(self, prop: Property) -> WriteResult[Property]:
        result = await self._inner.upsert_property(prop)
        if result.outcome != WriteOutcome.NOOP:
            await self._project("Property", prop.id, prop.model_dump(mode="json"))
        return result

    async def upsert_unit(self, unit: Unit) -> WriteResult[Unit]:
        result = await self._inner.upsert_unit(unit)
        if result.outcome != WriteOutcome.NOOP:
            await self._project("Unit", unit.id, unit.model_dump(mode="json"))
        return result

    async def upsert_lease(self, lease: Lease) -> WriteResult[Lease]:
        result = await self._inner.upsert_lease(lease)
        if result.outcome != WriteOutcome.NOOP:
            await self._project("Lease", lease.id, lease.model_dump(mode="json"))
        return result

    async def upsert_tenant(self, tenant: Tenant) -> WriteResult[Tenant]:
        result = await self._inner.upsert_tenant(tenant)
        if result.outcome != WriteOutcome.NOOP:
            await self._project("Tenant", tenant.id, tenant.model_dump(mode="json"))
        return result

    async def upsert_maintenance_request(
        self, request: MaintenanceRequest
    ) -> WriteResult[MaintenanceRequest]:
        result = await self._inner.upsert_maintenance_request(request)
        if result.outcome != WriteOutcome.NOOP:
            await self._project("MaintenanceRequest", request.id, request.model_dump(mode="json"))
        return result

    async def upsert_owner(self, owner: Owner) -> WriteResult[Owner]:
        result = await self._inner.upsert_owner(owner)
        if result.outcome != WriteOutcome.NOOP:
            await self._project("Owner", owner.id, owner.model_dump(mode="json"))
        return result

    async def upsert_vendor(self, vendor: Vendor) -> WriteResult[Vendor]:
        result = await self._inner.upsert_vendor(vendor)
        if result.outcome != WriteOutcome.NOOP:
            await self._project("Vendor", vendor.id, vendor.model_dump(mode="json"))
        return result

    async def upsert_action_item(self, item: ActionItem) -> WriteResult[ActionItem]:
        result = await self._inner.upsert_action_item(item)
        if result.outcome != WriteOutcome.NOOP:
            await self._project("ActionItem", item.id, item.model_dump(mode="json"))
        return result

    async def upsert_note(self, note: Note) -> WriteResult[Note]:
        result = await self._inner.upsert_note(note)
        if result.outcome != WriteOutcome.NOOP:
            await self._project("Note", note.id, note.model_dump(mode="json"))
        return result

    async def upsert_document(self, doc: Document) -> WriteResult[Document]:
        result = await self._inner.upsert_document(doc)
        if result.outcome != WriteOutcome.NOOP:
            await self._project("Document", doc.id, doc.model_dump(mode="json"))
        return result


PropertyStore.register(ProjectingPropertyStore)


def wrap_property_store_with_projection(
    inner: PropertyStore, projector: GraphProjector
) -> PropertyStore:
    """Return ``inner`` with post-upsert knowledge-graph edge projection."""
    return cast(PropertyStore, ProjectingPropertyStore(inner, projector))
