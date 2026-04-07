"""REST endpoints for the unified ontology layer.

Ontology CRUD operates through the KnowledgeGraph port.
Snapshot and subgraph endpoints go directly through PropertyStore —
the FK fields on core models ARE the graph edges.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from remi.agent.graph import ObjectTypeDef, PropertyDef
from remi.application.api.intelligence.ontology_schemas import (
    AggregateRequest,
    AggregateResponse,
    CodifyRequest,
    CodifyResponse,
    DefineTypeRequest,
    DefineTypeResponse,
    GraphEdge,
    GraphNode,
    ObjectResponse,
    OperationalEdge,
    OperationalGraphResponse,
    OperationalNode,
    RelatedResponse,
    SchemaListResponse,
    SchemaTypeResponse,
    SearchRequest,
    SearchResponse,
    SnapshotResponse,
    SubgraphResponse,
    TimelineResponse,
)
from remi.application.core.protocols import PropertyStore
from remi.application.infra.graph.schema import load_domain_yaml
from remi.shell.api.dependencies import Ctr
from remi.types.errors import NotFoundError

router = APIRouter(prefix="/ontology", tags=["ontology"])


# -- search -------------------------------------------------------------------


@router.get("/search/{type_name}", response_model=SearchResponse)
async def search_objects(
    type_name: str,
    c: Ctr,
    order_by: str | None = Query(None, description="Sort field (prefix with - for desc)"),
    limit: int = Query(50, ge=1, le=1000),
) -> SearchResponse:
    """Search objects of any type with optional field filters.

    Filters are passed as arbitrary query params beyond the declared ones.
    """
    results = await c.knowledge_graph.search_objects(
        type_name,
        order_by=order_by,
        limit=limit,
    )
    return SearchResponse(count=len(results), objects=results)


@router.post("/search/{type_name}", response_model=SearchResponse)
async def search_objects_post(
    type_name: str,
    body: SearchRequest,
    c: Ctr,
) -> SearchResponse:
    """Search with filters in the request body (for complex filter objects)."""
    results = await c.knowledge_graph.search_objects(
        type_name,
        filters=body.filters,
        order_by=body.order_by,
        limit=body.limit,
    )
    return SearchResponse(count=len(results), objects=results)


# -- get ----------------------------------------------------------------------


@router.get("/objects/{type_name}/{object_id}", response_model=ObjectResponse)
async def get_object(
    type_name: str,
    object_id: str,
    c: Ctr,
) -> ObjectResponse:
    """Get a single object by type and ID."""
    obj = await c.knowledge_graph.get_object(type_name, object_id)
    if obj is None:
        raise NotFoundError(type_name, object_id)
    return ObjectResponse(object=obj)


# -- related ------------------------------------------------------------------


@router.get(
    "/related/{object_id}",
    response_model=RelatedResponse,
)
async def get_related(
    object_id: str,
    c: Ctr,
    link_type: str | None = Query(None, description="Filter by link type"),
    direction: str = Query("both", description="both|outgoing|incoming"),
    max_depth: int = Query(1, ge=1, le=10, description="Traversal depth"),
) -> RelatedResponse:
    """Find related objects via link traversal."""
    if max_depth > 1:
        link_types = [link_type] if link_type else None
        nodes = await c.knowledge_graph.traverse(
            object_id,
            link_types=link_types,
            max_depth=max_depth,
        )
        return RelatedResponse(
            object_id=object_id,
            count=len(nodes),
            nodes=nodes,
            depth=max_depth,
        )

    links = await c.knowledge_graph.get_links(
        object_id,
        link_type=link_type,
        direction=direction,
    )
    return RelatedResponse(
        object_id=object_id,
        count=len(links),
        links=links,
    )


# -- aggregate ----------------------------------------------------------------


@router.post("/aggregate/{type_name}", response_model=AggregateResponse)
async def aggregate(
    type_name: str,
    body: AggregateRequest,
    c: Ctr,
) -> AggregateResponse:
    """Compute aggregate metrics (count, sum, avg, min, max) across objects."""
    result = await c.knowledge_graph.aggregate(
        type_name,
        body.metric,
        body.field,
        filters=body.filters,
        group_by=body.group_by,
    )
    return AggregateResponse(
        type_name=type_name,
        metric=body.metric,
        field=body.field,
        result=result,
    )


# -- timeline -----------------------------------------------------------------


@router.get(
    "/timeline/{type_name}/{object_id}",
    response_model=TimelineResponse,
)
async def get_timeline(
    type_name: str,
    object_id: str,
    c: Ctr,
    limit: int = Query(50, ge=1, le=1000),
) -> TimelineResponse:
    """Show event history for an object."""
    events = await c.knowledge_graph.get_timeline(
        type_name,
        object_id,
        limit=limit,
    )
    return TimelineResponse(
        object_type=type_name,
        object_id=object_id,
        count=len(events),
        events=events,
    )


# -- schema -------------------------------------------------------------------


@router.get("/schema", response_model=SchemaListResponse)
async def list_schema(c: Ctr) -> SchemaListResponse:
    """List all defined object types and link types."""
    types = await c.knowledge_graph.list_object_types()
    links = await c.knowledge_graph.list_link_types()
    return SchemaListResponse(
        types=[t.model_dump(mode="json") for t in types],
        link_types=[lt.model_dump(mode="json") for lt in links],
    )


@router.get("/schema/{type_name}", response_model=SchemaTypeResponse)
async def get_schema_type(
    type_name: str,
    c: Ctr,
) -> SchemaTypeResponse:
    """Describe a specific object type and its related link types."""
    ot = await c.knowledge_graph.get_object_type(type_name)
    if ot is None:
        raise NotFoundError("Type", type_name)
    links = await c.knowledge_graph.list_link_types()
    related = [
        lt.model_dump(mode="json")
        for lt in links
        if lt.source_type in (type_name, "*") or lt.target_type in (type_name, "*")
    ]
    return SchemaTypeResponse(type=ot.model_dump(mode="json"), related_links=related)


# -- snapshot (live graph visualization) --------------------------------------
#
# Built directly from PropertyStore + FK fields on core models.
# No KnowledgeGraph indirection — the domain models are the graph.
# ---------------------------------------------------------------------------


def _label(obj: object, field: str = "name") -> str:
    """Extract a display label from a Pydantic model."""
    val = getattr(obj, field, None)
    if val is None:
        val = getattr(obj, "id", "")
    if hasattr(val, "street"):
        return str(val.street)[:80]
    return str(val)[:80]


def _node(
    type_name: str,
    obj: object,
    label_field: str,
    display_fields: tuple[str, ...],
) -> GraphNode:
    label = _label(obj, label_field)
    props = {}
    for f in display_fields:
        v = getattr(obj, f, None)
        if v is not None:
            props[f] = v.model_dump(mode="json") if hasattr(v, "model_dump") else v
    return GraphNode(id=getattr(obj, "id", ""), type_name=type_name, label=label, properties=props)


def _edge(source_id: str, link_type: str, target_id: str) -> GraphEdge | None:
    if source_id and target_id:
        return GraphEdge(source_id=source_id, target_id=target_id, link_type=link_type)
    return None


async def _build_snapshot(
    ps: PropertyStore,
    *,
    manager_id: str | None = None,
    owner_id: str | None = None,
) -> SnapshotResponse:
    """Assemble graph snapshot directly from PropertyStore + FK fields."""
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    counts: dict[str, int] = {}
    edge_counts: dict[str, int] = {}
    node_ids: set[str] = set()

    def add(
        type_name: str,
        items: list[object],
        label_field: str,
        display: tuple[str, ...],
    ) -> None:
        added = 0
        for obj in items:
            n = _node(type_name, obj, label_field, display)
            if n.id in node_ids:
                continue
            nodes.append(n)
            node_ids.add(n.id)
            added += 1
        counts[type_name] = added

    seen_edges: set[tuple[str, str, str]] = set()

    def link(src: str, lt: str, tgt: str) -> None:
        e = _edge(src, lt, tgt)
        if not e or e.source_id not in node_ids or e.target_id not in node_ids:
            return
        key = (e.source_id, e.link_type, e.target_id)
        if key in seen_edges:
            return
        seen_edges.add(key)
        edges.append(e)
        edge_counts[lt] = edge_counts.get(lt, 0) + 1

    # --- Load all entities ---
    managers = await ps.list_managers()
    owners = await ps.list_owners()
    properties = await ps.list_properties(manager_id=manager_id, owner_id=owner_id)
    prop_ids = {p.id for p in properties}

    units = await ps.list_units()
    leases = await ps.list_leases()
    tenants = await ps.list_tenants()
    vendors = await ps.list_vendors()
    maint = await ps.list_maintenance_requests()

    # Scope units/leases/maint to properties in view
    if manager_id or owner_id:
        units = [u for u in units if u.property_id in prop_ids]
    unit_ids = {u.id for u in units}
    if manager_id or owner_id:
        leases = [ls for ls in leases if ls.property_id in prop_ids or ls.unit_id in unit_ids]
        maint = [m for m in maint if m.property_id in prop_ids or m.unit_id in unit_ids]

    tenant_ids_in_scope = {ls.tenant_id for ls in leases}
    if manager_id or owner_id:
        tenants = [t for t in tenants if t.id in tenant_ids_in_scope]

    vendor_ids_in_scope = {m.vendor_id for m in maint if m.vendor_id}
    if manager_id or owner_id:
        vendors = [v for v in vendors if v.id in vendor_ids_in_scope]
        mgr_ids_in_scope = {p.manager_id for p in properties if p.manager_id}
        managers = [m for m in managers if m.id in mgr_ids_in_scope or m.id == manager_id]
        owner_ids_in_scope = {p.owner_id for p in properties if p.owner_id}
        owners = [o for o in owners if o.id in owner_ids_in_scope or o.id == owner_id]

    # --- Build nodes ---
    add("PropertyManager", managers, "name", ("name", "email", "company"))
    add("Owner", owners, "name", ("name", "email"))
    add("Property", properties, "name", ("name", "address", "property_type"))
    add("Unit", units, "unit_number", ("unit_number", "market_rent", "bedrooms", "sqft"))
    add("Lease", leases, "status", ("status", "monthly_rent", "start_date", "end_date"))
    add("Tenant", tenants, "name", ("name", "email", "status"))
    add("Vendor", vendors, "name", ("name", "category"))
    add("MaintenanceRequest", maint, "title", ("title", "priority", "status", "category"))

    # --- Documents ---
    documents = await ps.list_documents()
    if manager_id or owner_id:
        documents = [
            d
            for d in documents
            if (d.manager_id and d.manager_id in {m.id for m in managers})
            or (d.property_id and d.property_id in prop_ids)
        ]
    add("Document", documents, "filename", ("filename", "report_type", "kind", "row_count"))

    # --- Derive edges from FK fields (the models are the graph) ---
    for p in properties:
        if p.manager_id:
            link(p.id, "MANAGED_BY", p.manager_id)
        if p.owner_id:
            link(p.id, "OWNED_BY", p.owner_id)

    for u in units:
        link(u.id, "BELONGS_TO", u.property_id)

    for ls in leases:
        link(ls.id, "COVERS", ls.unit_id)
        link(ls.id, "SIGNED_BY", ls.tenant_id)

    for m in maint:
        link(m.id, "AFFECTS", m.unit_id)
        if m.vendor_id:
            link(m.id, "SERVICED_BY", m.vendor_id)

    for d in documents:
        if d.property_id:
            link(d.id, "DOCUMENTS", d.property_id)
        if d.manager_id:
            link(d.id, "DOCUMENTS", d.manager_id)

    # Provenance: entity → source document (EXTRACTED_FROM)
    all_entities = (
        list(managers)
        + list(owners)
        + list(properties)
        + list(units)
        + list(leases)
        + list(tenants)
        + list(vendors)
        + list(maint)
    )
    for ent in all_entities:
        doc_id = getattr(ent, "source_document_id", None)
        if doc_id:
            link(ent.id, "EXTRACTED_FROM", doc_id)

    return SnapshotResponse(
        nodes=nodes,
        edges=edges,
        counts=counts,
        edge_counts=edge_counts,
        total_nodes=len(nodes),
        total_edges=len(edges),
    )


@router.get("/snapshot", response_model=SnapshotResponse)
async def graph_snapshot(
    c: Ctr,
    manager_id: str | None = Query(None, description="Scope to manager"),
    owner_id: str | None = Query(None, description="Scope to owner"),
) -> SnapshotResponse:
    """Full graph state built directly from core domain models.

    The FK fields on the models ARE the edges. No KnowledgeGraph
    indirection — PropertyStore is the source of truth.
    """
    return await _build_snapshot(
        c.property_store,
        manager_id=manager_id,
        owner_id=owner_id,
    )


# -- subgraph (ego-graph) ----------------------------------------------------


@router.get("/subgraph/{entity_id}", response_model=SubgraphResponse)
async def graph_subgraph(
    entity_id: str,
    c: Ctr,
    depth: int = Query(2, ge=1, le=4, description="Traversal depth"),
) -> SubgraphResponse:
    """Ego-graph around an entity — nodes and edges together.

    Fetches the full snapshot and then BFS-prunes to the requested depth
    from the center entity. For small-to-medium portfolios this is fast
    enough; for large graphs, a targeted traversal would be better.
    """
    full = await _build_snapshot(c.property_store)
    adj: dict[str, set[str]] = {}
    for e in full.edges:
        adj.setdefault(e.source_id, set()).add(e.target_id)
        adj.setdefault(e.target_id, set()).add(e.source_id)

    visited: set[str] = {entity_id}
    frontier = {entity_id}
    for _ in range(depth):
        next_frontier: set[str] = set()
        for nid in frontier:
            next_frontier |= adj.get(nid, set()) - visited
        visited |= next_frontier
        frontier = next_frontier
        if not frontier:
            break

    sub_nodes = [n for n in full.nodes if n.id in visited]
    sub_edges = [e for e in full.edges if e.source_id in visited and e.target_id in visited]

    return SubgraphResponse(
        center_id=entity_id,
        nodes=sub_nodes,
        edges=sub_edges,
    )


# -- operational graph (domain.yaml visualization) ---------------------------


def _build_operational_graph() -> OperationalGraphResponse:
    """Extract operational knowledge from domain.yaml into a visualization graph."""
    domain = load_domain_yaml()
    tbox = domain.get("tbox", {})
    abox = domain.get("abox", {})

    nodes: list[OperationalNode] = []
    edges: list[OperationalEdge] = []
    seen_ids: set[str] = set()
    processes: list[str] = []

    def add_node(node: OperationalNode) -> None:
        if node.id not in seen_ids:
            nodes.append(node)
            seen_ids.add(node.id)

    for process_name, process_data in tbox.items():
        if not isinstance(process_data, dict):
            continue
        processes.append(process_name)

        for sig in process_data.get("signals", []):
            sid = f"signal:{sig['name']}"
            add_node(
                OperationalNode(
                    id=sid,
                    kind="signal",
                    label=sig["name"].replace("_", " "),
                    process=process_name,
                    properties={
                        "severity": sig.get("severity", ""),
                        "entity": sig.get("entity", ""),
                        "description": sig.get("description", ""),
                    },
                )
            )

        for pol in process_data.get("policies", []):
            pid = pol.get("id", f"policy:{process_name}:{pol.get('description', '')[:20]}")
            add_node(
                OperationalNode(
                    id=pid,
                    kind="policy",
                    label=pol.get("description", pid)[:60],
                    process=process_name,
                    properties={
                        "trigger": pol.get("trigger", ""),
                        "deontic": pol.get("deontic", ""),
                    },
                )
            )

        for chain in process_data.get("causal_chains", []):
            cause_id = f"cause:{process_name}:{chain['cause']}"
            effect_id = f"effect:{process_name}:{chain['effect']}"
            add_node(
                OperationalNode(
                    id=cause_id,
                    kind="cause",
                    label=chain["cause"].replace("_", " "),
                    process=process_name,
                    properties={"description": chain.get("description", "")},
                )
            )
            add_node(
                OperationalNode(
                    id=effect_id,
                    kind="effect",
                    label=chain["effect"].replace("_", " "),
                    process=process_name,
                    properties={"description": chain.get("description", "")},
                )
            )
            edges.append(
                OperationalEdge(
                    source_id=cause_id,
                    target_id=effect_id,
                    link_type="CAUSES",
                )
            )

    for wf in abox.get("workflows", []):
        wf_name = wf["name"]
        wf_id = f"workflow:{wf_name}"
        process = wf_name if wf_name in processes else "operations"
        add_node(
            OperationalNode(
                id=wf_id,
                kind="workflow",
                label=wf_name.replace("_", " ").title(),
                process=process,
            )
        )
        steps = wf.get("steps", [])
        prev_id: str | None = None
        for step in steps:
            step_id = step["id"]
            add_node(
                OperationalNode(
                    id=step_id,
                    kind="step",
                    label=step.get("description", step_id)[:50],
                    process=process,
                )
            )
            edges.append(
                OperationalEdge(
                    source_id=wf_id,
                    target_id=step_id,
                    link_type="CONTAINS",
                )
            )
            if prev_id:
                edges.append(
                    OperationalEdge(
                        source_id=prev_id,
                        target_id=step_id,
                        link_type="FOLLOWS",
                    )
                )
            prev_id = step_id

    return OperationalGraphResponse(nodes=nodes, edges=edges, processes=processes)


@router.get("/graph/operational", response_model=OperationalGraphResponse)
async def operational_graph() -> OperationalGraphResponse:
    """Operational intelligence graph — workflows, causal chains, policies, signals.

    Renders the seeded operational knowledge from domain.yaml as a directed graph
    suitable for the Operational Intelligence Map visualization.
    """
    return _build_operational_graph()


# -- codify -------------------------------------------------------------------


@router.post("/codify", response_model=CodifyResponse)
async def codify(
    body: CodifyRequest,
    c: Ctr,
) -> CodifyResponse:
    """Codify operational knowledge into the ontology."""
    entity_id = await c.knowledge_graph.codify(
        body.knowledge_type,
        body.data,
        provenance=body.provenance,
    )

    if body.source_id and body.target_id:
        link_type = "CAUSES" if body.knowledge_type == "causal_link" else "RELATED_TO"
        await c.knowledge_graph.put_link(
            body.source_id,
            link_type,
            body.target_id,
            properties={"knowledge_id": entity_id},
        )

    return CodifyResponse(entity_id=entity_id, knowledge_type=body.knowledge_type)


# -- define -------------------------------------------------------------------


@router.post("/define", response_model=DefineTypeResponse)
async def define_type(
    body: DefineTypeRequest,
    c: Ctr,
) -> DefineTypeResponse:
    """Define a new object type in the ontology."""
    props = tuple(
        PropertyDef(
            name=p.name,
            data_type=p.data_type,
            required=p.required,
            description=p.description,
        )
        for p in body.properties
    )
    type_def = ObjectTypeDef(
        name=body.name,
        description=body.description,
        properties=props,
        provenance=body.provenance,
    )
    await c.knowledge_graph.define_object_type(type_def)
    return DefineTypeResponse(type=type_def.model_dump(mode="json"))
