"""Generic document ingestion for unrecognized report types.

When no source adapter claims the document, store every row as a KB entity
keyed by row index. No domain models are created — the data is preserved for
the LLM enrichment step and for future adapter development.
"""

from __future__ import annotations

from typing import Any

import structlog

from remi.documents.types import Document
from remi.graph.stores import KnowledgeStore
from remi.graph.types import Entity
from remi.ingestion.base import IngestionResult

logger = structlog.get_logger(__name__)


async def ingest_generic(
    doc: Document,
    namespace: str,
    result: IngestionResult,
    kb: KnowledgeStore,
) -> None:
    if not doc.rows:
        logger.warning("generic_ingest_empty", doc_id=doc.id)
        return

    for row_idx, row in enumerate(doc.rows):
        entity_id = f"row:{doc.id}:{row_idx}"
        props: dict[str, Any] = {
            k: v for k, v in row.items() if v is not None
        }
        props["source_doc"] = doc.id
        props["row_index"] = row_idx

        await kb.put_entity(
            Entity(
                entity_id=entity_id,
                entity_type="unknown_row",
                namespace=namespace,
                properties=props,
            )
        )
        result.entities_created += 1

    result.ambiguous_rows = list(doc.rows)

    logger.info(
        "generic_ingest_complete",
        doc_id=doc.id,
        rows_stored=len(doc.rows),
    )
