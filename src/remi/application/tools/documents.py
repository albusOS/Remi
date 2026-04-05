"""Document tools — in-process calls to DocumentStore and ingestion pipeline.

Provides: document_list, document_query, document_search, ingest_document.
"""

from __future__ import annotations

from typing import Any

from remi.agent.documents import DocumentStore
from remi.agent.types import ToolArg, ToolDefinition, ToolProvider, ToolRegistry
from remi.application.core.protocols import VectorSearch
from remi.application.services.ingestion.pipeline import DocumentIngestService


class DocumentToolProvider(ToolProvider):
    def __init__(
        self,
        document_store: DocumentStore,
        document_ingest: DocumentIngestService | None = None,
        vector_search: VectorSearch | None = None,
    ) -> None:
        self._document_store = document_store
        self._document_ingest = document_ingest
        self._vector_search = vector_search

    def register(self, registry: ToolRegistry) -> None:
        store = self._document_store

        # -- document_list ---------------------------------------------------------

        async def document_list(args: dict[str, Any]) -> Any:
            docs = await store.list_documents()
            return [
                {
                    "id": d.id,
                    "filename": d.filename,
                    "kind": d.kind.value,
                    "columns": d.column_names,
                    "row_count": d.row_count,
                    "chunk_count": len(d.chunks),
                    "page_count": d.page_count,
                    "tags": d.tags,
                    "uploaded_at": d.uploaded_at.isoformat(),
                    "report_type": d.metadata.get("report_type"),
                }
                for d in docs
            ]

        registry.register(
            "document_list",
            document_list,
            ToolDefinition(
                name="document_list",
                description=(
                    "List all documents in the knowledge base with metadata "
                    "(filename, kind, columns/chunks, tags, upload date)."
                ),
                args=[],
            ),
        )

        # -- document_query --------------------------------------------------------

        async def document_query(args: dict[str, Any]) -> Any:
            doc_id = args.get("document_id")
            query = args.get("query")
            filters = args.get("filters")
            limit = int(args.get("limit", 50))

            if doc_id:
                maybe = await store.get(doc_id)
                docs = [maybe] if maybe is not None else []
            else:
                docs = await store.list_documents()

            if not docs:
                return {"rows": [], "chunks": [], "total": 0}

            all_rows: list[dict[str, Any]] = []
            all_chunks: list[dict[str, Any]] = []

            for doc in docs:
                if doc.kind.value == "tabular":
                    rows = await store.query_rows(doc.id, filters=filters, limit=limit * 2)
                    for row in rows:
                        row["_document_id"] = doc.id
                        row["_filename"] = doc.filename
                    all_rows.extend(rows)
                elif doc.kind.value == "text":
                    for chunk in doc.chunks[:limit * 2]:
                        entry: dict[str, Any] = {
                            "_document_id": doc.id,
                            "_filename": doc.filename,
                            "chunk_index": chunk.index,
                            "page": chunk.page,
                            "text": chunk.text,
                        }
                        all_chunks.append(entry)

            if query:
                q_lower = query.lower()
                all_rows = [
                    r
                    for r in all_rows
                    if any(q_lower in str(v).lower() for v in r.values())
                ]
                all_chunks = [
                    c for c in all_chunks
                    if q_lower in c.get("text", "").lower()
                ]

            return {
                "rows": all_rows[:limit],
                "chunks": all_chunks[:limit],
                "total": len(all_rows) + len(all_chunks),
            }

        registry.register(
            "document_query",
            document_query,
            ToolDefinition(
                name="document_query",
                description=(
                    "Search knowledge base documents. For tabular docs (reports), searches rows. "
                    "For text docs (PDFs, contracts), searches text chunks. "
                    "Can filter by document_id, text query, or column filters."
                ),
                args=[
                    ToolArg(
                        name="document_id", description="Specific document ID (omit to search all)"
                    ),
                    ToolArg(name="query", description="Text search across content"),
                    ToolArg(
                        name="filters",
                        description="Column filters (tabular docs only) as JSON object.",
                        type="object",
                    ),
                    ToolArg(
                        name="limit", description="Max results to return (default: 50)",
                        type="integer",
                    ),
                ],
            ),
        )

        # -- document_search -------------------------------------------------------

        if self._vector_search is not None:
            vs = self._vector_search

            async def document_search(args: dict[str, Any]) -> Any:
                query = args.get("query", "")
                limit = int(args.get("limit", 10))
                if not query.strip():
                    return {"results": [], "total": 0}

                results = await vs.semantic_search(
                    query,
                    limit=limit,
                    min_score=0.25,
                    metadata_filter=None,
                )

                doc_types = {"DocumentRow", "DocumentChunk"}
                hits = [
                    {
                        "entity_id": r.entity_id,
                        "entity_type": r.entity_type,
                        "text": r.text[:500],
                        "score": round(r.score, 3),
                        "filename": r.metadata.get("filename", ""),
                        "page": r.metadata.get("page"),
                        "document_id": r.metadata.get("document_id", ""),
                    }
                    for r in results
                    if r.entity_type in doc_types
                ]
                return {"results": hits, "total": len(hits)}

            registry.register(
                "document_search",
                document_search,
                ToolDefinition(
                    name="document_search",
                    description=(
                        "Semantic search across all knowledge base documents. "
                        "Finds relevant passages from PDFs, contracts, reports, and other "
                        "uploaded files using vector similarity. Returns matching text snippets "
                        "with source document info."
                    ),
                    args=[
                        ToolArg(
                            name="query",
                            description="Natural language search query",
                            required=True,
                        ),
                        ToolArg(
                            name="limit",
                            description="Max results (default: 10)",
                            type="integer",
                        ),
                    ],
                ),
            )

        # -- ingest_document -------------------------------------------------------
        # Only registered when the ingestion service is available (API context).

        if self._document_ingest is not None:
            ingest = self._document_ingest

            async def ingest_document(args: dict[str, Any]) -> Any:
                import aiofiles

                file_path = args.get("file_path", "")
                manager = args.get("manager")

                try:
                    async with aiofiles.open(file_path, "rb") as f:
                        content = await f.read()
                except (OSError, FileNotFoundError) as exc:
                    return {"error": f"Cannot read file: {exc}"}

                from pathlib import Path as _Path

                suffix = _Path(file_path).suffix.lower()
                _ct_map = {
                    ".csv": "text/csv",
                    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    ".xls": "application/vnd.ms-excel",
                    ".pdf": "application/pdf",
                    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    ".txt": "text/plain",
                    ".md": "text/markdown",
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".png": "image/png",
                    ".gif": "image/gif",
                    ".webp": "image/webp",
                }
                content_type = _ct_map.get(suffix, "application/octet-stream")
                filename = _Path(file_path).name

                result = await ingest.ingest_upload(
                    filename, content, content_type, manager=manager
                )
                return {
                    "doc_id": result.doc.id,
                    "filename": result.doc.filename,
                    "report_type": result.report_type,
                    "entities_extracted": result.entities_extracted,
                    "relationships_extracted": result.relationships_extracted,
                    "pipeline_warnings": result.pipeline_warnings,
                }

            registry.register(
                "ingest_document",
                ingest_document,
                ToolDefinition(
                    name="ingest_document",
                    description=(
                        "Ingest a document file through the LLM extraction pipeline. "
                        "Classifies the report type, extracts all rows into domain entities, "
                        "enriches unknown rows, and runs the signal pipeline. "
                        "Use this when a new report file is available and needs to be processed."
                    ),
                    args=[
                        ToolArg(
                            name="file_path",
                            description="Absolute path to the document file to ingest",
                            required=True,
                        ),
                        ToolArg(
                            name="manager",
                            description="Optional manager tag to associate with the document",
                        ),
                    ],
                ),
            )
