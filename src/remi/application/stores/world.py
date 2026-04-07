"""RE WorldModel — live view over PropertyStore with FK-derived links.

The agent kernel sees ``WorldModel`` (search, get, get_links, schema).
This implementation fulfills that contract by wrapping PropertyStore
and deriving relationship edges from FK fields at query time — no
separate graph store, no projection step, no data duplication.
"""

from __future__ import annotations

from typing import Any

from remi.agent.graph.retrieval.introspect import pydantic_to_type_defs
from remi.agent.graph.stores import WorldModel
from remi.agent.graph.types import GraphLink, GraphObject, ObjectTypeDef
from remi.application.core.models import (
    BalanceObservation,
    Lease,
    MaintenanceRequest,
    Property,
    PropertyManager,
    Tenant,
    Unit,
)
from remi.application.core.protocols import PropertyStore

_MODEL_REGISTRY: list[tuple[type, str]] = [
    (PropertyManager, "Person or company managing one or more properties"),
    (Property, "A real-estate asset — building, complex, or single-family home"),
    (Unit, "A rentable unit within a property"),
    (Lease, "A rental agreement between a tenant and a unit"),
    (Tenant, "An individual or entity renting a unit"),
    (MaintenanceRequest, "A work order for a unit or common area"),
    (BalanceObservation, "A point-in-time snapshot of a tenant's outstanding balance"),
]


def _to_graph_object(entity_id: str, type_name: str, model: Any) -> GraphObject:
    props = model.model_dump(mode="json") if hasattr(model, "model_dump") else {}
    return GraphObject(id=entity_id, type_name=type_name, properties=props)


class REWorldModel(WorldModel):
    """Real-estate world model backed by PropertyStore."""

    def __init__(self, property_store: PropertyStore) -> None:
        self._ps = property_store

    async def search_objects(
        self,
        query: str,
        *,
        object_type: str | None = None,
        limit: int = 20,
    ) -> list[GraphObject]:
        q = query.lower()
        results: list[GraphObject] = []

        if object_type is None or object_type in ("PropertyManager", "Manager"):
            for m in await self._ps.list_managers():
                if q in m.name.lower() or q in (m.email or "").lower():
                    results.append(_to_graph_object(m.id, "PropertyManager", m))

        if object_type is None or object_type == "Property":
            for p in await self._ps.list_properties():
                if q in p.name.lower() or q in str(p.address).lower():
                    results.append(_to_graph_object(p.id, "Property", p))

        if object_type is None or object_type == "Tenant":
            for t in await self._ps.list_tenants():
                if q in getattr(t, "name", "").lower():
                    results.append(_to_graph_object(t.id, "Tenant", t))

        if object_type is None or object_type == "Unit":
            for u in await self._ps.list_units():
                if q in getattr(u, "unit_number", "").lower() or q in u.id.lower():
                    results.append(_to_graph_object(u.id, "Unit", u))

        return results[:limit]

    async def get_object(self, object_id: str) -> GraphObject | None:
        for getter, type_name in [
            (self._ps.get_manager, "PropertyManager"),
            (self._ps.get_property, "Property"),
            (self._ps.get_unit, "Unit"),
            (self._ps.get_lease, "Lease"),
            (self._ps.get_tenant, "Tenant"),
            (self._ps.get_maintenance_request, "MaintenanceRequest"),
        ]:
            entity = await getter(object_id)
            if entity is not None:
                return _to_graph_object(object_id, type_name, entity)
        return None

    async def get_links(
        self,
        object_id: str,
        *,
        direction: str = "both",
        link_type: str | None = None,
    ) -> list[GraphLink]:
        links: list[GraphLink] = []

        def _add(source: str, lt: str, target: str) -> None:
            if link_type and lt != link_type:
                return
            if direction == "outgoing" and source != object_id:
                return
            if direction == "incoming" and target != object_id:
                return
            links.append(GraphLink(source_id=source, link_type=lt, target_id=target))

        prop = await self._ps.get_property(object_id)
        if prop is not None:
            if prop.manager_id:
                _add(object_id, "MANAGED_BY", prop.manager_id)
            for u in await self._ps.list_units(property_id=object_id):
                _add(object_id, "HAS_UNIT", u.id)
            for le in await self._ps.list_leases(property_id=object_id):
                _add(object_id, "HAS_LEASE", le.id)
            for mx in await self._ps.list_maintenance_requests(property_id=object_id):
                _add(object_id, "HAS_MAINTENANCE", mx.id)
            return links

        unit = await self._ps.get_unit(object_id)
        if unit is not None:
            if unit.property_id:
                _add(object_id, "BELONGS_TO", unit.property_id)
            if getattr(unit, "lease_id", None):
                _add(object_id, "HAS_LEASE", unit.lease_id)
            return links

        lease = await self._ps.get_lease(object_id)
        if lease is not None:
            if getattr(lease, "property_id", None):
                _add(object_id, "BELONGS_TO", lease.property_id)
            if getattr(lease, "unit_id", None):
                _add(object_id, "FOR_UNIT", lease.unit_id)
            if getattr(lease, "tenant_id", None):
                _add(object_id, "HAS_TENANT", lease.tenant_id)
            return links

        tenant = await self._ps.get_tenant(object_id)
        if tenant is not None:
            for le in await self._ps.list_leases(tenant_id=object_id):
                _add(object_id, "HAS_LEASE", le.id)
            return links

        mx = await self._ps.get_maintenance_request(object_id)
        if mx is not None:
            if getattr(mx, "property_id", None):
                _add(object_id, "BELONGS_TO", mx.property_id)
            if getattr(mx, "unit_id", None):
                _add(object_id, "FOR_UNIT", mx.unit_id)
            return links

        mgr = await self._ps.get_manager(object_id)
        if mgr is not None:
            for p in await self._ps.list_properties(manager_id=object_id):
                _add(object_id, "MANAGES", p.id)
            return links

        return links

    async def schema(self) -> list[ObjectTypeDef]:
        return pydantic_to_type_defs(_MODEL_REGISTRY)  # type: ignore[arg-type]


def build_re_world_model(property_store: PropertyStore) -> REWorldModel:
    """Factory: create the RE world model backed by PropertyStore."""
    return REWorldModel(property_store)
