"""Graph tools — LLM-driven entity and link management.

Provides: store_entity, link_entities, query_graph.

The LLM decides types, relations, and property shapes at runtime.
The store enforces nothing — the schema lives in the LLM's reasoning.
"""

from __future__ import annotations

import json
from typing import Any

import structlog

from remi.agent.graph.stores import EntityStore, WorldModel
from remi.agent.graph.types import GraphLink, GraphObject
from remi.agent.types import ToolArg, ToolDefinition, ToolProvider, ToolRegistry

logger = structlog.get_logger(__name__)


class GraphToolProvider(ToolProvider):
    """Registers graph mutation and query tools on the shared registry."""

    def __init__(
        self,
        entity_store: EntityStore,
        world_model: WorldModel | None = None,
    ) -> None:
        self._entity_store = entity_store
        self._world_model = world_model

    def register(self, registry: ToolRegistry) -> None:
        entity_store = self._entity_store
        world_model = self._world_model

        # -- store_entity -------------------------------------------------------

        async def store_entity(args: dict[str, Any]) -> Any:
            eid = args["id"]
            type_name = args["type"]
            properties = args.get("properties") or {}
            if isinstance(properties, str):
                properties = json.loads(properties)
            await entity_store.put_entity(eid, type_name, properties)
            logger.info("graph_entity_stored", id=eid, type=type_name)
            return {"stored": True, "id": eid, "type": type_name}

        registry.register(
            "store_entity",
            store_entity,
            ToolDefinition(
                name="store_entity",
                description=(
                    "Create or update an entity in the knowledge graph. "
                    "Merges properties if the entity already exists."
                ),
                args=[
                    ToolArg(
                        name="id",
                        description="Stable slug ID, e.g. 'property:123-main-st'",
                        required=True,
                    ),
                    ToolArg(
                        name="type",
                        description="PascalCase entity type, e.g. 'Property', 'Tenant'",
                        required=True,
                    ),
                    ToolArg(
                        name="properties",
                        description="JSON object of entity properties",
                        required=True,
                    ),
                ],
            ),
        )

        # -- link_entities ------------------------------------------------------

        async def link_entities(args: dict[str, Any]) -> Any:
            source_id = args["source_id"]
            target_id = args["target_id"]
            relation = args["relation"]
            properties = args.get("properties") or {}
            if isinstance(properties, str):
                properties = json.loads(properties)
            await entity_store.put_link(source_id, target_id, relation, properties)
            logger.info(
                "graph_link_stored",
                source=source_id,
                target=target_id,
                relation=relation,
            )
            return {
                "linked": True,
                "source_id": source_id,
                "target_id": target_id,
                "relation": relation,
            }

        registry.register(
            "link_entities",
            link_entities,
            ToolDefinition(
                name="link_entities",
                description=(
                    "Create or update a directed relationship between two entities. "
                    "Use UPPER_SNAKE_CASE relation names like MANAGED_BY, HAS_UNIT."
                ),
                args=[
                    ToolArg(
                        name="source_id",
                        description="ID of the source entity",
                        required=True,
                    ),
                    ToolArg(
                        name="target_id",
                        description="ID of the target entity",
                        required=True,
                    ),
                    ToolArg(
                        name="relation",
                        description="UPPER_SNAKE_CASE relation type, e.g. 'MANAGED_BY'",
                        required=True,
                    ),
                    ToolArg(
                        name="properties",
                        description="Optional JSON object of edge properties",
                    ),
                ],
            ),
        )

        # -- query_graph --------------------------------------------------------

        async def query_graph(args: dict[str, Any]) -> Any:
            question = args["question"]
            type_filter = args.get("type")
            limit = int(args.get("limit", 10))

            entities: list[GraphObject] = []
            neighborhood: list[GraphLink] = []

            entity_results = await entity_store.find_entities(
                question, type_name=type_filter, limit=limit,
            )
            entities.extend(entity_results)

            if world_model is not None:
                world_results = await world_model.search_objects(
                    question, object_type=type_filter, limit=limit,
                )
                seen_ids = {e.id for e in entities}
                for obj in world_results:
                    if obj.id not in seen_ids:
                        entities.append(obj)
                        seen_ids.add(obj.id)

            entities = entities[:limit]

            for entity in entities:
                es_links = await entity_store.get_links(entity.id)
                neighborhood.extend(es_links)
                if world_model is not None:
                    wm_links = await world_model.get_links(entity.id)
                    neighborhood.extend(wm_links)

            return {
                "entities": [
                    {"id": e.id, "type": e.type_name, "properties": e.properties}
                    for e in entities
                ],
                "links": [
                    {
                        "source": lnk.source_id,
                        "relation": lnk.link_type,
                        "target": lnk.target_id,
                    }
                    for lnk in _dedup_links(neighborhood)
                ],
            }

        registry.register(
            "query_graph",
            query_graph,
            ToolDefinition(
                name="query_graph",
                description=(
                    "Search the knowledge graph by natural language. Returns "
                    "matching entities and their one-hop neighborhood links. "
                    "Searches both the relational world model and the open-ended "
                    "entity store."
                ),
                args=[
                    ToolArg(
                        name="question",
                        description="Natural language search query",
                        required=True,
                    ),
                    ToolArg(
                        name="type",
                        description="Optional entity type filter, e.g. 'Property'",
                    ),
                    ToolArg(
                        name="limit",
                        description="Max entities to return (default 10)",
                    ),
                ],
            ),
        )


def _dedup_links(links: list[GraphLink]) -> list[GraphLink]:
    seen: set[tuple[str, str, str]] = set()
    result: list[GraphLink] = []
    for lnk in links:
        key = (lnk.source_id, lnk.link_type, lnk.target_id)
        if key not in seen:
            seen.add(key)
            result.append(lnk)
    return result
