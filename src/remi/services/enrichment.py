"""Enrichment types and helpers shared by ingestion and LLM adapters.

Layer 3 (Services): parsing enricher agent output into KnowledgeStore
entities/relationships, plus the callback type alias for enrichment.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

import structlog

from remi.models.documents import Document
from remi.models.memory import Entity, KnowledgeStore, Relationship

_log = structlog.get_logger(__name__)

EnrichFn = Callable[
    [list[dict[str, Any]], Document, KnowledgeStore],
    Awaitable[tuple[int, int]],
]


async def parse_enricher_output(
    output: Any,
    namespace: str,
    kb: KnowledgeStore,
) -> tuple[int, int]:
    """Parse the enricher agent's JSON output and write to the KnowledgeStore."""
    entities_count = 0
    rels_count = 0

    if isinstance(output, str):
        try:
            output = json.loads(output)
        except (json.JSONDecodeError, TypeError):
            _log.warning("enricher_output_not_json", output_preview=output[:200])
            return 0, 0

    if not isinstance(output, dict):
        return 0, 0

    for row_data in output.get("rows", []):
        for ent in row_data.get("entities", []):
            etype = ent.get("entity_type", "unknown")
            eid = ent.get("entity_id", "")
            if not eid:
                continue
            await kb.put_entity(
                Entity(
                    entity_id=eid,
                    entity_type=etype,
                    namespace=namespace,
                    properties=ent.get("properties", {}),
                    metadata={"source": "llm_enrichment", "row_index": row_data.get("row_index")},
                )
            )
            entities_count += 1

        for rel in row_data.get("relationships", []):
            src = rel.get("source_id", "")
            tgt = rel.get("target_id", "")
            rtype = rel.get("relation_type", "")
            if src and tgt and rtype:
                await kb.put_relationship(
                    Relationship(
                        source_id=src,
                        target_id=tgt,
                        relation_type=rtype,
                        namespace=namespace,
                    )
                )
                rels_count += 1

    return entities_count, rels_count
