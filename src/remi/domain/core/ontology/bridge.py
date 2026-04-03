"""RE-specific wiring of PropertyStore into a BridgedKnowledgeGraph.

This is the real-estate factory — maps entity repos to core_types bindings.
"""

from __future__ import annotations

from remi.agent.graph.adapters.bridge import BridgedKnowledgeGraph, CoreTypeBindings
from remi.agent.graph.stores import KnowledgeStore
from remi.domain.core.portfolio.protocols import PropertyStore


def build_knowledge_graph(
    property_store: PropertyStore,
    knowledge_store: KnowledgeStore,
) -> BridgedKnowledgeGraph:
    """Factory: wire REMI's PropertyStore methods into a BridgedKnowledgeGraph."""
    ps = property_store
    core_types: CoreTypeBindings = {
        "PropertyManager": (ps.get_manager, ps.list_managers),
        "Portfolio": (ps.get_portfolio, ps.list_portfolios),
        "Property": (ps.get_property, ps.list_properties),
        "Unit": (ps.get_unit, ps.list_units),
        "Lease": (ps.get_lease, ps.list_leases),
        "Tenant": (ps.get_tenant, ps.list_tenants),
        "MaintenanceRequest": (ps.get_maintenance_request, ps.list_maintenance_requests),
        "ActionItem": (ps.get_action_item, ps.list_action_items),
    }
    return BridgedKnowledgeGraph(knowledge_store, core_types=core_types)
