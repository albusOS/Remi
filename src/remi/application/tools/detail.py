"""Entity detail handler — 360-degree views for any entity type.

``EntityDetailHandler.resolve`` is the single entry point.  It parses the
``entity_type`` from the tool call and dispatches to the appropriate
``_detail_*`` method, each of which fans out parallel store fetches to build
a complete entity graph including all connected sub-entities.

The ``fields`` frozenset lets callers request only the sub-entities they need,
avoiding unnecessary fetches and token-heavy responses.
"""

from __future__ import annotations

import asyncio
from typing import Any

from remi.application.core.protocols import PropertyStore


class EntityDetailHandler:
    """Fetches a 360-degree view of any entity and all its connections.

    Supported entity types: manager, property, tenant, lease, document.
    Pass ``fields`` to request only specific sub-entities and reduce response size.
    """

    def __init__(self, property_store: PropertyStore) -> None:
        self._ps = property_store

    async def resolve(
        self,
        entity_type: str,
        entity_id: str,
        fields: frozenset[str] | None,
    ) -> dict[str, Any]:
        """Dispatch to the correct detail method based on entity_type."""
        if entity_type == "manager":
            return await self._detail_manager(entity_id, fields=fields)
        if entity_type == "property":
            return await self._detail_property(entity_id, fields=fields)
        if entity_type == "tenant":
            return await self._detail_tenant(entity_id, fields=fields)
        if entity_type == "lease":
            return await self._detail_lease(entity_id, fields=fields)
        if entity_type == "document":
            return await self._detail_document(entity_id, fields=fields)
        return {
            "error": (
                f"Unknown entity_type {entity_type!r}. "
                "Use: manager, property, tenant, lease, document"
            )
        }

    # -- Per-entity detail fetchers -----------------------------------------------

    async def _detail_manager(
        self, manager_id: str, *, fields: frozenset[str] | None = None
    ) -> dict[str, Any]:
        want = fields.__contains__ if fields else lambda _: True
        manager = await self._ps.get_manager(manager_id)
        if manager is None:
            return {"error": f"Manager '{manager_id}' not found"}
        result: dict[str, Any] = {
            "entity_type": "manager",
            "manager": manager.model_dump(mode="json"),
        }

        fetch_props = fields is None or want("properties")
        fetch_units = fields is None or want("units")
        fetch_leases = fields is None or want("leases")
        fetch_tenants = fields is None or want("tenants")
        fetch_maintenance = fields is None or want("maintenance_requests")
        fetch_documents = fields is None or want("documents")
        fetch_actions = fields is None or want("action_items")
        fetch_notes = fields is None or want("notes")

        coros: list[Any] = []
        keys: list[str] = []
        if fetch_props:
            coros.append(self._ps.list_properties(manager_id=manager_id))
            keys.append("properties")
        if fetch_actions:
            coros.append(self._ps.list_action_items(manager_id=manager_id))
            keys.append("action_items")
        if fetch_notes:
            coros.append(
                self._ps.list_notes(entity_type="PropertyManager", entity_id=manager_id)
            )
            keys.append("notes")
        if fetch_documents:
            coros.append(self._ps.list_documents(manager_id=manager_id))
            keys.append("documents")
        if fetch_maintenance:
            coros.append(self._ps.list_maintenance_requests(manager_id=manager_id))
            keys.append("maintenance_requests")

        gathered = await asyncio.gather(*coros)
        raw: dict[str, Any] = dict(zip(keys, gathered, strict=True))

        properties = raw.get("properties", [])
        prop_ids = {p.id for p in properties}

        if fetch_units or fetch_leases or fetch_tenants:
            unit_coros = (
                [self._ps.list_units(property_id=pid) for pid in prop_ids]
                if (fetch_units or fetch_tenants)
                else []
            )
            lease_coros = (
                [self._ps.list_leases(property_id=pid) for pid in prop_ids]
                if (fetch_leases or fetch_tenants)
                else []
            )
            units_grps, leases_grps = await asyncio.gather(
                asyncio.gather(*unit_coros),
                asyncio.gather(*lease_coros),
            )
            flat_units = [u.model_dump(mode="json") for grp in units_grps for u in grp]
            flat_leases = [ls.model_dump(mode="json") for grp in leases_grps for ls in grp]

            if fetch_tenants:
                tenant_ids = {ls["tenant_id"] for ls in flat_leases if ls.get("tenant_id")}
                tenants = await asyncio.gather(*[self._ps.get_tenant(tid) for tid in tenant_ids])
                result["tenants"] = [t.model_dump(mode="json") for t in tenants if t is not None]
            if fetch_units:
                result["units"] = flat_units
            if fetch_leases:
                result["leases"] = flat_leases

        if fetch_props:
            result["properties"] = [p.model_dump(mode="json") for p in properties]
        if fetch_maintenance:
            result["maintenance_requests"] = [
                m.model_dump(mode="json") for m in raw.get("maintenance_requests", [])
            ]
        if fetch_documents:
            result["documents"] = [d.model_dump(mode="json") for d in raw.get("documents", [])]
        if fetch_actions:
            result["action_items"] = [
                ai.model_dump(mode="json") for ai in raw.get("action_items", [])
            ]
        if fetch_notes:
            result["notes"] = [n.model_dump(mode="json") for n in raw.get("notes", [])]
        return result

    async def _detail_property(
        self, property_id: str, *, fields: frozenset[str] | None = None
    ) -> dict[str, Any]:
        want = fields.__contains__ if fields else lambda _: True
        prop = await self._ps.get_property(property_id)
        if prop is None:
            return {"error": f"Property '{property_id}' not found"}

        coros: list[Any] = []
        keys: list[str] = []
        if fields is None or want("units"):
            coros.append(self._ps.list_units(property_id=property_id))
            keys.append("units")
        if fields is None or want("leases") or want("tenants"):
            coros.append(self._ps.list_leases(property_id=property_id))
            keys.append("leases")
        if fields is None or want("maintenance_requests"):
            coros.append(self._ps.list_maintenance_requests(property_id=property_id))
            keys.append("maintenance_requests")
        if fields is None or want("documents"):
            coros.append(self._ps.list_documents(property_id=property_id))
            keys.append("documents")
        if fields is None or want("action_items"):
            coros.append(self._ps.list_action_items(property_id=property_id))
            keys.append("action_items")
        if fields is None or want("notes"):
            coros.append(
                self._ps.list_notes(entity_type="Property", entity_id=property_id)
            )
            keys.append("notes")

        gathered = await asyncio.gather(*coros)
        raw: dict[str, Any] = dict(zip(keys, gathered, strict=True))
        leases = raw.get("leases", [])

        manager: Any = None
        if fields is None or want("manager"):
            manager = await self._ps.get_manager(prop.manager_id) if prop.manager_id else None

        tenants: list[Any] = []
        if fields is None or want("tenants"):
            tenant_ids = {ls.tenant_id for ls in leases if ls.tenant_id}
            tenants_raw = await asyncio.gather(*[self._ps.get_tenant(tid) for tid in tenant_ids])
            tenants = [t for t in tenants_raw if t is not None]

        result: dict[str, Any] = {
            "entity_type": "property",
            "property": prop.model_dump(mode="json"),
        }
        if fields is None or want("manager"):
            result["manager"] = manager.model_dump(mode="json") if manager else None
        if "units" in raw:
            result["units"] = [u.model_dump(mode="json") for u in raw["units"]]
        if "leases" in raw and (fields is None or want("leases")):
            result["leases"] = [ls.model_dump(mode="json") for ls in leases]
        if tenants or (fields is None or want("tenants")):
            result["tenants"] = [t.model_dump(mode="json") for t in tenants]
        if "maintenance_requests" in raw:
            result["maintenance_requests"] = [
                m.model_dump(mode="json") for m in raw["maintenance_requests"]
            ]
        if "documents" in raw:
            result["documents"] = [d.model_dump(mode="json") for d in raw["documents"]]
        if "action_items" in raw:
            result["action_items"] = [ai.model_dump(mode="json") for ai in raw["action_items"]]
        if "notes" in raw:
            result["notes"] = [n.model_dump(mode="json") for n in raw["notes"]]
        return result

    async def _detail_tenant(
        self, tenant_id: str, *, fields: frozenset[str] | None = None
    ) -> dict[str, Any]:
        want = fields.__contains__ if fields else lambda _: True
        tenant = await self._ps.get_tenant(tenant_id)
        if tenant is None:
            return {"error": f"Tenant '{tenant_id}' not found"}

        coros: list[Any] = []
        keys: list[str] = []
        # Leases are always fetched — they're needed to derive properties/units/managers
        coros.append(self._ps.list_leases(tenant_id=tenant_id))
        keys.append("leases")
        if fields is None or want("balance_history"):
            coros.append(self._ps.list_balance_observations(tenant_id=tenant_id))
            keys.append("balance_history")
        if fields is None or want("action_items"):
            coros.append(self._ps.list_action_items(tenant_id=tenant_id))
            keys.append("action_items")
        if fields is None or want("notes"):
            coros.append(self._ps.list_notes(entity_type="Tenant", entity_id=tenant_id))
            keys.append("notes")

        gathered = await asyncio.gather(*coros)
        raw: dict[str, Any] = dict(zip(keys, gathered, strict=True))
        leases = raw.get("leases", [])
        property_ids = {ls.property_id for ls in leases if ls.property_id}
        unit_ids = {ls.unit_id for ls in leases if ls.unit_id}

        fetch_props = fields is None or want("properties") or want("managers")
        fetch_units = fields is None or want("units") or want("maintenance_requests")

        properties_raw: list[Any] = []
        units_raw: list[Any] = []
        if fetch_props or fetch_units:
            prop_coros = (
                [self._ps.get_property(pid) for pid in property_ids] if fetch_props else []
            )
            unit_coros = (
                [self._ps.get_unit(uid) for uid in unit_ids] if fetch_units else []
            )
            props_results, units_results = await asyncio.gather(
                asyncio.gather(*prop_coros),
                asyncio.gather(*unit_coros),
            )
            properties_raw = [p for p in props_results if p is not None]
            units_raw = [u for u in units_results if u is not None]

        managers_raw: list[Any] = []
        if fields is None or want("managers"):
            manager_ids = {p.manager_id for p in properties_raw if p.manager_id}
            managers_results = await asyncio.gather(
                *[self._ps.get_manager(mid) for mid in manager_ids]
            )
            managers_raw = [m for m in managers_results if m is not None]

        maintenance_requests: list[dict[str, Any]] = []
        if fields is None or want("maintenance_requests"):
            for uid in unit_ids:
                reqs = await self._ps.list_maintenance_requests(unit_id=uid)
                maintenance_requests.extend(r.model_dump(mode="json") for r in reqs)

        result: dict[str, Any] = {
            "entity_type": "tenant",
            "tenant": tenant.model_dump(mode="json"),
        }
        if fields is None or want("leases"):
            result["leases"] = [ls.model_dump(mode="json") for ls in leases]
        if fields is None or want("properties"):
            result["properties"] = [p.model_dump(mode="json") for p in properties_raw]
        if fields is None or want("units"):
            result["units"] = [u.model_dump(mode="json") for u in units_raw]
        if fields is None or want("managers"):
            result["managers"] = [m.model_dump(mode="json") for m in managers_raw]
        if fields is None or want("balance_history"):
            result["balance_history"] = [
                b.model_dump(mode="json") for b in raw.get("balance_history", [])
            ]
        if maintenance_requests or (fields is None or want("maintenance_requests")):
            result["maintenance_requests"] = maintenance_requests
        if fields is None or want("action_items"):
            result["action_items"] = [
                ai.model_dump(mode="json") for ai in raw.get("action_items", [])
            ]
        if fields is None or want("notes"):
            result["notes"] = [n.model_dump(mode="json") for n in raw.get("notes", [])]
        return result

    async def _detail_lease(
        self, lease_id: str, *, fields: frozenset[str] | None = None
    ) -> dict[str, Any]:
        want = fields.__contains__ if fields else lambda _: True
        lease = await self._ps.get_lease(lease_id)
        if lease is None:
            return {"error": f"Lease '{lease_id}' not found"}

        coros: list[Any] = []
        keys: list[str] = []
        if fields is None or want("tenant"):
            coros.append(
                self._ps.get_tenant(lease.tenant_id) if lease.tenant_id else asyncio.sleep(0)
            )
            keys.append("tenant")
        if fields is None or want("unit"):
            coros.append(
                self._ps.get_unit(lease.unit_id) if lease.unit_id else asyncio.sleep(0)
            )
            keys.append("unit")
        if fields is None or want("property") or want("manager"):
            coros.append(
                self._ps.get_property(lease.property_id)
                if lease.property_id
                else asyncio.sleep(0)
            )
            keys.append("property")
        if fields is None or want("documents"):
            coros.append(self._ps.list_documents(lease_id=lease_id))
            keys.append("documents")
        if fields is None or want("notes"):
            coros.append(self._ps.list_notes(entity_type="Lease", entity_id=lease_id))
            keys.append("notes")
        if fields is None or want("balance_history"):
            coros.append(
                self._ps.list_balance_observations(tenant_id=lease.tenant_id)
                if lease.tenant_id
                else asyncio.sleep(0)
            )
            keys.append("balance_history")

        gathered = await asyncio.gather(*coros)
        raw: dict[str, Any] = dict(zip(keys, gathered, strict=True))

        prop = raw.get("property") if hasattr(raw.get("property"), "model_dump") else None
        manager: Any = None
        if fields is None or want("manager"):
            manager = (
                await self._ps.get_manager(prop.manager_id) if prop and prop.manager_id else None
            )

        result: dict[str, Any] = {"entity_type": "lease", "lease": lease.model_dump(mode="json")}
        if fields is None or want("tenant"):
            t = raw.get("tenant")
            result["tenant"] = t.model_dump(mode="json") if t and hasattr(t, "model_dump") else None
        if fields is None or want("unit"):
            u = raw.get("unit")
            result["unit"] = u.model_dump(mode="json") if u and hasattr(u, "model_dump") else None
        if fields is None or want("property"):
            result["property"] = prop.model_dump(mode="json") if prop else None
        if fields is None or want("manager"):
            result["manager"] = manager.model_dump(mode="json") if manager else None
        if fields is None or want("documents"):
            result["documents"] = [d.model_dump(mode="json") for d in raw.get("documents", [])]
        if fields is None or want("balance_history"):
            bh = raw.get("balance_history", [])
            result["balance_history"] = (
                [b.model_dump(mode="json") for b in bh] if isinstance(bh, list) else []
            )
        if fields is None or want("notes"):
            result["notes"] = [n.model_dump(mode="json") for n in raw.get("notes", [])]
        return result

    async def _detail_document(
        self, doc_id: str, *, fields: frozenset[str] | None = None
    ) -> dict[str, Any]:
        want = fields.__contains__ if fields else lambda _: True
        doc = await self._ps.get_document(doc_id)
        if doc is None:
            return {"error": f"Document '{doc_id}' not found"}

        coros: list[Any] = []
        keys: list[str] = []
        if fields is None or want("property"):
            coros.append(
                self._ps.get_property(doc.property_id) if doc.property_id else asyncio.sleep(0)
            )
            keys.append("property")
        if fields is None or want("manager"):
            coros.append(
                self._ps.get_manager(doc.manager_id) if doc.manager_id else asyncio.sleep(0)
            )
            keys.append("manager")
        if fields is None or want("unit"):
            coros.append(
                self._ps.get_unit(doc.unit_id) if doc.unit_id else asyncio.sleep(0)
            )
            keys.append("unit")
        if fields is None or want("lease"):
            coros.append(
                self._ps.get_lease(doc.lease_id) if doc.lease_id else asyncio.sleep(0)
            )
            keys.append("lease")

        gathered = await asyncio.gather(*coros)
        raw: dict[str, Any] = dict(zip(keys, gathered, strict=True))

        result: dict[str, Any] = {
            "entity_type": "document",
            "document": doc.model_dump(mode="json"),
        }
        for key in ("property", "manager", "unit", "lease"):
            if fields is None or want(key):
                val = raw.get(key)
                result[key] = val.model_dump(mode="json") if val and hasattr(val, "model_dump") else None
        return result
