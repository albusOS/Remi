"""Intelligence tools — search, trends, fact assertion, and context annotation."""

from __future__ import annotations

from typing import Any

import structlog

from remi.agent.events import EventBus
from remi.agent.signals import DomainSchema
from remi.agent.types import ToolArg, ToolDefinition, ToolProvider, ToolRegistry
from remi.application.core.events import EventStore
from remi.application.core.protocols import PropertyStore

from .assertions import add_context, assert_fact
from .search import SearchService
from .trends import TrendResolver

_log = structlog.get_logger(__name__)

_QUERY_OPERATIONS = (
    "search, delinquency_trend, occupancy_trend, rent_trend, maintenance_trend, "
    "ontology_schema, entity_graph"
)


class IntelligenceToolProvider(ToolProvider):
    """Registers intelligence tools: search, trends, assert_fact, add_context."""

    def __init__(
        self,
        *,
        search_service: SearchService,
        trend_resolver: TrendResolver,
        property_store: PropertyStore,
        domain_schema: DomainSchema | None = None,
        event_store: EventStore | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._search = search_service
        self._trends = trend_resolver
        self._ps = property_store
        self._domain_schema = domain_schema
        self._event_store = event_store
        self._event_bus = event_bus

    def register(self, registry: ToolRegistry) -> None:
        self._register_intelligence_query(registry)
        self._register_assert_fact(registry)
        self._register_add_context(registry)

    def _register_intelligence_query(self, registry: ToolRegistry) -> None:
        dispatch = {
            "search": self._search_op,
            "delinquency_trend": self._delinquency_trend_op,
            "occupancy_trend": self._occupancy_trend_op,
            "rent_trend": self._rent_trend_op,
            "maintenance_trend": self._maintenance_trend_op,
            "ontology_schema": self._ontology_schema_op,
            "entity_graph": self._entity_graph_op,
        }

        async def intelligence_query(args: dict[str, Any]) -> Any:
            operation = args.get("operation", "")
            if not operation:
                return {"error": "operation is required", "available": _QUERY_OPERATIONS}
            handler = dispatch.get(operation)
            if handler is None:
                return {
                    "error": f"Unknown operation: {operation!r}",
                    "available": _QUERY_OPERATIONS,
                }
            try:
                return await handler(args)
            except Exception as exc:
                _log.warning("intelligence_query_error", operation=operation, exc_info=True)
                return {"error": f"{operation} failed: {exc}"}

        registry.register(
            "intelligence_query",
            intelligence_query,
            ToolDefinition(
                name="intelligence_query",
                description=(
                    "Intelligence analytics — entity search, time-series trends, "
                    "and ontology queries (domain schema + entity graph). "
                    "Note: entity counts reflect ingested data only — zero means not yet "
                    "uploaded, not absent from the real portfolio. "
                    f"Operations: {_QUERY_OPERATIONS}."
                ),
                args=[
                    ToolArg(
                        name="operation",
                        description=f"One of: {_QUERY_OPERATIONS}",
                        required=True,
                    ),
                    ToolArg(name="query", description="Search text (for 'search')"),
                    ToolArg(
                        name="manager_id",
                        description="Scope to a manager (trends, entity_graph)",
                    ),
                    ToolArg(name="property_id", description="Scope trends to a property"),
                    ToolArg(name="periods", description="Number of periods for trend (default: 12)"),
                ],
            ),
        )

    def _register_assert_fact(self, registry: ToolRegistry) -> None:
        ps = self._ps
        event_store = self._event_store
        event_bus = self._event_bus

        async def _assert_fact(args: dict[str, Any]) -> dict[str, str]:
            props = args.get("properties", {})
            if isinstance(props, str):
                import json
                props = json.loads(props)
            return await assert_fact(
                ps,
                event_store,
                event_bus,
                entity_type=args.get("entity_type", ""),
                entity_id=args.get("entity_id"),
                properties=props,
                related_to=args.get("related_to"),
                relation_type=args.get("relation_type"),
            )

        registry.register(
            "assert_fact",
            _assert_fact,
            ToolDefinition(
                name="assert_fact",
                description=(
                    "Record a new fact or observation. Creates a note with "
                    "user-level provenance (highest confidence). Optionally "
                    "note a relationship to an existing entity."
                ),
                args=[
                    ToolArg(name="entity_type", description="Entity type name", required=True),
                    ToolArg(
                        name="properties",
                        description="Entity properties as JSON",
                        type="object",
                        required=True,
                    ),
                    ToolArg(name="entity_id", description="Optional entity ID"),
                    ToolArg(name="related_to", description="ID of entity to link to"),
                    ToolArg(name="relation_type", description="Link type for relation"),
                ],
            ),
        )

    def _register_add_context(self, registry: ToolRegistry) -> None:
        ps = self._ps

        async def _add_context(args: dict[str, Any]) -> dict[str, str]:
            return await add_context(
                ps,
                entity_type=args.get("entity_type", ""),
                entity_id=args.get("entity_id", ""),
                context=args.get("context", ""),
            )

        registry.register(
            "add_context",
            _add_context,
            ToolDefinition(
                name="add_context",
                description=(
                    "Attach user context to an entity — e.g. 'we are in a dispute "
                    "with this tenant' or 'this property is being renovated'."
                ),
                args=[
                    ToolArg(name="entity_type", description="Entity type name", required=True),
                    ToolArg(name="entity_id", description="Entity ID to annotate", required=True),
                    ToolArg(name="context", description="Context text to attach", required=True),
                ],
            ),
        )

    async def _search_op(self, args: dict[str, Any]) -> dict[str, Any]:
        q = args.get("query", "")
        if not q:
            return {"error": "query is required for search"}
        results = await self._search.search(q)
        return {"results": [r.model_dump(mode="json") for r in results]}

    async def _delinquency_trend_op(self, args: dict[str, Any]) -> dict[str, Any]:
        result = await self._trends.delinquency_trend(
            manager_id=args.get("manager_id"),
            property_id=args.get("property_id"),
            periods=int(args.get("periods", 12)),
        )
        return result.model_dump(mode="json")

    async def _occupancy_trend_op(self, args: dict[str, Any]) -> dict[str, Any]:
        result = await self._trends.occupancy_trend(
            manager_id=args.get("manager_id"),
            property_id=args.get("property_id"),
            periods=int(args.get("periods", 12)),
        )
        return result.model_dump(mode="json")

    async def _rent_trend_op(self, args: dict[str, Any]) -> dict[str, Any]:
        result = await self._trends.rent_trend(
            manager_id=args.get("manager_id"),
            property_id=args.get("property_id"),
            periods=int(args.get("periods", 12)),
        )
        return result.model_dump(mode="json")

    async def _maintenance_trend_op(self, args: dict[str, Any]) -> dict[str, Any]:
        result = await self._trends.maintenance_trend(
            manager_id=args.get("manager_id"),
            property_id=args.get("property_id"),
            periods=int(args.get("periods", 12)),
        )
        return result.model_dump(mode="json")

    async def _ontology_schema_op(self, args: dict[str, Any]) -> dict[str, Any]:
        """Return the domain schema: entity types, relationships, and processes."""
        if self._domain_schema is None:
            return {"error": "Domain schema not available"}
        schema = self._domain_schema
        return {
            "entity_types": [
                {
                    "name": et.name,
                    "description": et.description,
                    "key_fields": et.key_fields,
                }
                for et in schema.entity_types
            ],
            "relationships": [
                {"name": rel.name, "source": rel.source, "target": rel.target}
                for rel in schema.relationships
            ],
            "processes": [
                {
                    "name": proc.name,
                    "description": proc.description,
                    "involves": proc.involves,
                }
                for proc in schema.processes
            ],
        }

    async def _entity_graph_op(self, args: dict[str, Any]) -> dict[str, Any]:
        """Return entity counts per type and key relationship summary."""
        ps = self._ps
        manager_id: str | None = args.get("manager_id")

        managers = await ps.list_managers()
        owners = await ps.list_owners()
        properties = await ps.list_properties(manager_id=manager_id)
        units = await ps.list_units()
        leases = await ps.list_leases()
        tenants = await ps.list_tenants()
        maint = await ps.list_maintenance_requests()
        documents = await ps.list_documents()

        prop_ids = {p.id for p in properties}
        if manager_id:
            units = [u for u in units if u.property_id in prop_ids]
            unit_ids = {u.id for u in units}
            leases = [
                ls for ls in leases if ls.property_id in prop_ids or ls.unit_id in unit_ids
            ]
            maint = [
                m for m in maint if m.property_id in prop_ids or m.unit_id in unit_ids
            ]
            tenant_ids = {ls.tenant_id for ls in leases}
            tenants = [t for t in tenants if t.id in tenant_ids]

        return {
            "counts": {
                "managers": len(managers),
                "owners": len(owners),
                "properties": len(properties),
                "units": len(units),
                "leases": len(leases),
                "tenants": len(tenants),
                "maintenance_requests": len(maint),
                "documents": len(documents),
            },
            "relationships": [
                {"type": "Property MANAGED_BY PropertyManager"},
                {"type": "Property OWNED_BY Owner"},
                {"type": "Unit BELONGS_TO Property"},
                {"type": "Lease COVERS Unit"},
                {"type": "Lease SIGNED_BY Tenant"},
                {"type": "MaintenanceRequest AFFECTS Unit"},
            ],
            "data_note": (
                "Counts reflect only what has been ingested so far from uploaded documents. "
                "A zero count means no data for that entity type has been uploaded yet — "
                "not that those entities don't exist in the real portfolio. "
                "Data is always partial and accumulates incrementally as reports are uploaded."
            ),
        }
