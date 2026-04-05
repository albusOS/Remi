"""IngestionService — pipeline-driven entity extraction from uploaded documents.

All documents go through the ``document_ingestion`` pipeline
(classify -> extract -> enrich).  The pipeline calls LLMProvider directly
-- no chat runtime, no sandbox session overhead.

The resolver maps LLM-extracted rows directly to domain models and persists
them to PropertyStore and KnowledgeStore in one pass.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import structlog

from remi.agent.pipeline import IngestionPipelineRunner
from remi.application.core.protocols import (
    KBEntity,
    KBRelationship,
    KnowledgeWriter,
    ParsedDocument,
    PropertyStore,
)
from remi.application.infra.ontology.schema import entity_schemas_for_prompt
from remi.application.services.ingestion.base import IngestionResult
from remi.application.services.ingestion.managers import ManagerResolver
from remi.application.services.ingestion.persist import resolve_and_persist
from remi.application.services.ingestion.resolver import PERSISTABLE_TYPES
from remi.application.services.ingestion.validation import validate_rows

logger = structlog.get_logger(__name__)

_PIPELINE = "document_ingestion"


# ---------------------------------------------------------------------------
# Typed models for LLM pipeline output
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EnrichedRelationship:
    source_id: str
    target_id: str
    relation_type: str


@dataclass(frozen=True)
class EnrichedRow:
    row_index: int
    entity_type: str
    entity_id: str
    properties: dict[str, str | int | float | bool | None]
    relationships: list[EnrichedRelationship] = field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: object) -> EnrichedRow | None:
        if not isinstance(raw, dict):
            return None
        eid = str(raw.get("entity_id", "")).strip()
        etype = str(raw.get("entity_type", "")).strip()
        if not eid or not etype:
            return None
        rels: list[EnrichedRelationship] = []
        for r in raw.get("relationships", []) or []:
            if not isinstance(r, dict):
                continue
            src = str(r.get("source_id", "")).strip()
            tgt = str(r.get("target_id", "")).strip()
            rtype = str(r.get("relation_type", "")).strip()
            if src and tgt and rtype:
                rels.append(EnrichedRelationship(src, tgt, rtype))
        props_raw = raw.get("properties") or {}
        props: dict[str, str | int | float | bool | None] = {
            str(k): v
            for k, v in props_raw.items()
            if isinstance(v, (str, int, float, bool, type(None)))
        }
        return cls(
            row_index=int(raw.get("row_index", 0)),
            entity_type=etype,
            entity_id=eid,
            properties=props,
            relationships=rels,
        )


@dataclass(frozen=True)
class KnownTypeDescription:
    type: str
    description: str

    def to_dict(self) -> dict[str, str]:
        return {"type": self.type, "description": self.description}


_KNOWN_TYPES: list[KnownTypeDescription] = [
    KnownTypeDescription(
        type="rent_roll",
        description=(
            "Lists every unit in the portfolio with occupancy status, lease dates, "
            "rent, and vacancy days. Has section headers like Current / Vacant-Unrented."
        ),
    ),
    KnownTypeDescription(
        type="delinquency",
        description=(
            "Shows tenants with outstanding balances: amount owed, 0-30 day and 30+ "
            "day buckets, last payment date, tenant status (Current / Notice / Evict)."
        ),
    ),
    KnownTypeDescription(
        type="lease_expiration",
        description=(
            "Details upcoming lease expirations: move-in date, lease-end date, rent "
            "vs market rent, sqft, tenant name. Tags column often carries manager name."
        ),
    ),
    KnownTypeDescription(
        type="property_directory",
        description=(
            "Listing of all properties with assigned property manager and address. "
            "Some properties may have no manager assigned."
        ),
    ),
]


class IngestionService:
    """Extracts entities from documents via the LLM ingestion pipeline
    and persists typed domain models into PropertyStore."""

    def __init__(
        self,
        knowledge_writer: KnowledgeWriter,
        property_store: PropertyStore,
        pipeline_runner: IngestionPipelineRunner,
    ) -> None:
        self._kb = knowledge_writer
        self._ps = property_store
        self._runner = pipeline_runner
        self._manager_resolver = ManagerResolver(
            manager_repo=property_store,
            portfolio_repo=property_store,
        )

    async def ingest_mapped_rows(
        self,
        doc: ParsedDocument,
        *,
        report_type: str,
        rows: list[dict[str, Any]],
        manager: str | None = None,
    ) -> IngestionResult:
        """Persist pre-mapped rows without calling the LLM pipeline.

        Used by the rule-based extraction path where column mapping has
        already been done deterministically.
        """
        namespace = "ontology"
        result = IngestionResult(document_id=doc.id)
        result.report_type = report_type

        upload_portfolio_id: str | None = None
        if manager:
            upload_portfolio_id = await self._manager_resolver.ensure_manager(manager)

        validated = validate_rows(rows, result)
        if validated:
            await resolve_and_persist(
                validated,
                report_type=report_type,
                platform="appfolio",
                doc_id=doc.id,
                namespace=namespace,
                kb=self._kb,
                ps=self._ps,
                manager_resolver=self._manager_resolver,
                result=result,
                upload_portfolio_id=upload_portfolio_id,
            )
        else:
            logger.warning(
                "rules_mapped_rows_empty_after_validation",
                doc_id=doc.id,
                report_type=report_type,
            )

        await self._write_doc_entity(doc, result, namespace)

        logger.info(
            "rules_ingestion_complete",
            doc_id=doc.id,
            report_type=report_type,
            entities=result.entities_created,
            relationships=result.relationships_created,
            rows_accepted=result.rows_accepted,
            rows_rejected=result.rows_rejected,
        )
        return result

    async def ingest(
        self,
        doc: ParsedDocument,
        *,
        manager: str | None = None,
    ) -> IngestionResult:
        namespace = "ontology"
        result = IngestionResult(document_id=doc.id)

        upload_portfolio_id: str | None = None
        if manager:
            upload_portfolio_id = await self._manager_resolver.ensure_manager(manager)

        pipeline_input = json.dumps(
            {
                "column_names": doc.column_names,
                "sample_rows": doc.rows[:5],
                "all_rows": doc.rows,
                "known_types": [t.to_dict() for t in _KNOWN_TYPES],
            },
            default=str,
        )

        try:
            pipeline_result = await self._runner.run(
                _PIPELINE,
                pipeline_input,
                context={
                    "entity_schemas": entity_schemas_for_prompt(filter_names=PERSISTABLE_TYPES),
                },
            )
        except Exception:
            logger.exception("ingestion_pipeline_failed", doc_id=doc.id)
            await self._write_doc_entity(doc, result, namespace)
            return result

        extract_output = pipeline_result.step("extract")
        enrich_output = pipeline_result.step("enrich")

        if not isinstance(extract_output, dict):
            logger.warning(
                "extraction_output_not_dict",
                doc_id=doc.id,
                output_type=type(extract_output).__name__,
            )
            await self._write_doc_entity(doc, result, namespace)
            return result

        report_type = str(extract_output.get("report_type") or "unknown")
        platform = str(extract_output.get("platform") or "appfolio")
        raw_rows = extract_output.get("rows") or []
        unknown_rows = extract_output.get("unknown_rows") or []

        if not isinstance(raw_rows, list):
            raw_rows = []
        if not isinstance(unknown_rows, list):
            unknown_rows = []

        rows = [r for r in raw_rows if isinstance(r, dict)]
        result.report_type = report_type
        rows = validate_rows(rows, result)

        if rows:
            await resolve_and_persist(
                rows,
                report_type=report_type,
                platform=platform,
                doc_id=doc.id,
                namespace=namespace,
                kb=self._kb,
                ps=self._ps,
                manager_resolver=self._manager_resolver,
                result=result,
                upload_portfolio_id=upload_portfolio_id,
            )
        else:
            logger.warning(
                "extraction_produced_no_rows",
                doc_id=doc.id,
                filename=doc.filename,
                report_type=report_type,
            )

        if isinstance(enrich_output, dict):
            raw_enriched = enrich_output.get("enriched_rows") or []
            if isinstance(raw_enriched, list):
                enriched = [EnrichedRow.from_raw(r) for r in raw_enriched]
                await self._apply_enriched_rows(
                    [e for e in enriched if e is not None], namespace, result,
                    doc_id=doc.id,
                )
        elif unknown_rows:
            logger.info(
                "unknown_rows_not_enriched",
                doc_id=doc.id,
                count=len(unknown_rows),
            )

        await self._write_doc_entity(doc, result, namespace)

        logger.info(
            "ingestion_complete",
            doc_id=doc.id,
            report_type=result.report_type,
            entities=result.entities_created,
            relationships=result.relationships_created,
            prompt_tokens=pipeline_result.total_usage.prompt_tokens,
            completion_tokens=pipeline_result.total_usage.completion_tokens,
        )
        return result

    async def _apply_enriched_rows(
        self,
        enriched: list[EnrichedRow],
        namespace: str,
        result: IngestionResult,
        doc_id: str,
    ) -> None:
        for row in enriched:
            if row.entity_type == "noise":
                continue
            await self._kb.put_entity(
                KBEntity(
                    entity_id=row.entity_id,
                    entity_type=row.entity_type,
                    namespace=namespace,
                    properties={**row.properties, "document_id": doc_id},
                    metadata={"source": "llm_enrichment"},
                )
            )
            result.entities_created += 1
            for rel in row.relationships:
                await self._kb.put_relationship(
                    KBRelationship(
                        source_id=rel.source_id,
                        target_id=rel.target_id,
                        relation_type=rel.relation_type,
                        namespace=namespace,
                    )
                )
                result.relationships_created += 1

    async def _write_doc_entity(
        self,
        doc: ParsedDocument,
        result: IngestionResult,
        namespace: str,
    ) -> None:
        props: dict[str, str] = {
            "filename": doc.filename,
            "content_type": doc.content_type,
            "kind": doc.kind,
            "row_count": str(doc.row_count),
            "chunk_count": str(len(doc.chunks)),
            "page_count": str(doc.page_count),
            "report_type": result.report_type,
            "document_id": doc.id,
            "size_bytes": str(doc.size_bytes),
        }
        if doc.tags:
            props["tags"] = ",".join(doc.tags)

        await self._kb.put_entity(
            KBEntity(
                entity_id=f"document:{doc.id}",
                entity_type="document",
                namespace=namespace,
                properties=props,
            )
        )
