"""Portfolio-wide search — keyword + semantic hybrid over the vector index.

Exposes a fast, deterministic search (no LLM) suitable for typeahead UX.
Keyword matching fires first; semantic embedding only kicks in when
keyword results are sparse.
"""

from __future__ import annotations

from typing import Any

import structlog
from pydantic import BaseModel, Field

from remi.application.core.protocols import TextSearchHit, VectorSearch

_log = structlog.get_logger(__name__)

_KEYWORD_FIELDS = ["manager_name", "property_name", "tenant_name", "company"]

_ENTITY_TYPE_LABELS: dict[str, str] = {
    "PropertyManager": "Manager",
    "Property": "Property",
    "Tenant": "Tenant",
    "Unit": "Unit",
    "MaintenanceRequest": "Maintenance",
    "DocumentRow": "Document",
    "DocumentChunk": "Document",
}


class SearchHit(BaseModel, frozen=True):
    entity_id: str
    entity_type: str
    label: str
    title: str
    subtitle: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


def _title_for(hit: TextSearchHit) -> str:
    meta = hit.metadata
    et = hit.entity_type
    if et == "PropertyManager":
        return meta.get("manager_name", hit.entity_id)
    if et == "Property":
        return meta.get("property_name", hit.entity_id)
    if et == "Tenant":
        return meta.get("tenant_name", hit.entity_id)
    if et == "Unit":
        pname = meta.get("property_name", "")
        return f"Unit at {pname}" if pname else hit.entity_id
    if et == "MaintenanceRequest":
        pname = meta.get("property_name", "")
        return f"Maintenance — {pname}" if pname else "Maintenance Request"
    if et == "DocumentRow":
        return meta.get("filename", "Document Row")
    if et == "DocumentChunk":
        return meta.get("filename", "Document")
    return hit.entity_id


def _subtitle_for(hit: TextSearchHit) -> str:
    meta = hit.metadata
    et = hit.entity_type
    if et == "PropertyManager":
        parts: list[str] = []
        if meta.get("company"):
            parts.append(str(meta["company"]))
        if meta.get("property_count"):
            parts.append(f"{meta['property_count']} properties")
        return " · ".join(parts) if parts else ""
    if et == "Property":
        return meta.get("manager_name", "")
    if et == "Tenant":
        return meta.get("property_name", "")
    if et == "Unit":
        return meta.get("property_name", "")
    if et == "MaintenanceRequest":
        parts_m: list[str] = []
        if meta.get("priority"):
            parts_m.append(str(meta["priority"]))
        if meta.get("status"):
            parts_m.append(str(meta["status"]))
        return " · ".join(parts_m)
    if et == "DocumentRow":
        return meta.get("report_type", "")
    if et == "DocumentChunk":
        page = meta.get("page")
        return f"Page {page}" if page is not None else ""
    return ""


def _search_hit_from(raw: TextSearchHit) -> SearchHit:
    et = raw.entity_type
    return SearchHit(
        entity_id=raw.entity_id,
        entity_type=et,
        label=_ENTITY_TYPE_LABELS.get(et, et),
        title=_title_for(raw),
        subtitle=_subtitle_for(raw),
        score=raw.score,
        metadata=raw.metadata,
    )


class SearchService:
    """Hybrid keyword + semantic search over the vector index."""

    def __init__(self, vector_search: VectorSearch) -> None:
        self._vs = vector_search

    async def search(
        self,
        query: str,
        *,
        types: list[str] | None = None,
        manager_id: str | None = None,
        limit: int = 10,
    ) -> list[SearchHit]:
        if not query or not query.strip():
            return []

        query = query.strip()
        seen: dict[str, SearchHit] = {}

        keyword_results = await self._vs.keyword_search(
            query,
            fields=_KEYWORD_FIELDS,
            limit=limit * 2,
        )
        for r in keyword_results:
            hit = _search_hit_from(r)
            if types and hit.entity_type not in types:
                continue
            if manager_id and r.metadata.get("manager_id") != manager_id:
                continue
            if hit.entity_id not in seen:
                seen[hit.entity_id] = hit

        if len(seen) < limit:
            metadata_filter: dict[str, Any] | None = None
            if manager_id:
                metadata_filter = {"manager_id": manager_id}

            try:
                semantic_results = await self._vs.semantic_search(
                    query,
                    limit=limit,
                    min_score=0.3,
                    metadata_filter=metadata_filter,
                )
                for r in semantic_results:
                    hit = _search_hit_from(r)
                    if types and hit.entity_type not in types:
                        continue
                    if hit.entity_id not in seen or hit.score > seen[hit.entity_id].score:
                        seen[hit.entity_id] = hit
            except Exception:
                _log.warning("search_semantic_failed", query=query[:100], exc_info=True)

        results = sorted(seen.values(), key=lambda h: h.score, reverse=True)
        return results[:limit]
