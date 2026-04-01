"""LLM-backed callbacks injected into ingestion and document processing.

Layer 3 — Signals / Services.  These bridge ingestion services to the
agent chat loop and are constructed by the DI container.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

import structlog

from remi.documents.appfolio_schema import REPORT_TYPE_DESCRIPTIONS
from remi.models.documents import Document
from remi.models.memory import KnowledgeStore
from remi.services.enrichment import EnrichFn, parse_enricher_output

if TYPE_CHECKING:
    from remi.agent.runner import ChatAgentService
    from remi.config.settings import SecretsSettings

_log = structlog.get_logger(__name__)

ClassifyFn = Callable[[Document], Awaitable[str | None]]


def make_classify_fn(
    get_agent: Callable[[], ChatAgentService],
    secrets: SecretsSettings,
) -> ClassifyFn:
    """Build the LLM-backed document classifier callback.

    *get_agent* is a thunk so the callback can be wired before the
    ``ChatAgentService`` is constructed.
    """

    async def classify(doc: Document) -> str | None:
        if not secrets.has_any_llm_key:
            return None
        try:
            answer, _run_id = await get_agent().ask(
                "report_classifier",
                json.dumps(
                    {
                        "column_names": doc.column_names,
                        "sample_rows": doc.rows[:5],
                        "known_types": [
                            {"type": k, "description": v}
                            for k, v in REPORT_TYPE_DESCRIPTIONS.items()
                        ],
                    },
                    default=str,
                ),
            )
            if not answer:
                return None
            if isinstance(answer, str):
                answer = json.loads(answer)
            if isinstance(answer, dict):
                report_type = answer.get("report_type", "").strip().lower().replace(" ", "_")
                return report_type if report_type else None
        except Exception:
            _log.exception("classify_document_failed", doc_id=doc.id)
            return None
        return None

    return classify


def make_enrich_fn(
    get_agent: Callable[[], ChatAgentService],
    secrets: SecretsSettings,
) -> EnrichFn:
    """Build the LLM-backed row enrichment callback.

    *get_agent* is a thunk — see ``make_classify_fn`` for rationale.
    """

    async def enrich(
        rows: list[dict[str, Any]],
        doc: Document,
        knowledge_store: KnowledgeStore,
    ) -> tuple[int, int]:
        if not secrets.has_any_llm_key:
            return 0, 0
        namespace = f"doc:{doc.id}"
        batch_size = 20
        total_entities = 0
        total_rels = 0
        try:
            for i in range(0, len(rows), batch_size):
                batch = rows[i : i + batch_size]
                payload = json.dumps(
                    [{"row_index": i + j, **row} for j, row in enumerate(batch)],
                    default=str,
                )
                answer, _run_id = await get_agent().ask(
                    "knowledge_enricher",
                    payload,
                )
                if answer:
                    e, r = await parse_enricher_output(answer, namespace, knowledge_store)
                    total_entities += e
                    total_rels += r
        except Exception:
            _log.exception("enrich_rows_failed", doc_id=doc.id)
            return total_entities, total_rels
        return total_entities, total_rels

    return enrich
