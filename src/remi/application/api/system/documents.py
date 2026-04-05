"""Document upload and query REST endpoints — knowledge base API."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Body, Depends, File, Form, Query, UploadFile

from remi.agent.documents import DocumentKind, DocumentStore
from remi.application.api.dependencies import get_document_ingest, get_document_store
from remi.application.api.system.document_schemas import (
    ChunkItem,
    DeleteResponse,
    DocumentChunksResponse,
    DocumentDetail,
    DocumentListItem,
    DocumentListResponse,
    DocumentRowsResponse,
    KnowledgeInfo,
    TagsResponse,
    TagUpdateRequest,
    UploadResponse,
)
from remi.application.realtime.connection_manager import manager as ws_manager
from remi.application.services.ingestion.pipeline import DocumentIngestService
from remi.types.errors import DomainError, NotFoundError

_log = structlog.get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


def _list_item(d: "Document") -> DocumentListItem:  # type: ignore[name-defined]
    return DocumentListItem(
        id=d.id,
        filename=d.filename,
        content_type=d.content_type,
        kind=d.kind.value,
        row_count=d.row_count,
        columns=d.column_names,
        report_type=d.metadata.get("report_type", "unknown"),
        chunk_count=len(d.chunks),
        page_count=d.page_count,
        tags=d.tags,
        size_bytes=d.size_bytes,
        uploaded_at=d.uploaded_at.isoformat(),
    )


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    manager: str | None = Form(default=None),
    ingest: DocumentIngestService = Depends(get_document_ingest),
) -> UploadResponse:
    """Upload a file to the knowledge base.

    Accepts CSV, Excel, PDF, Word, text files, and images. Tabular files
    (CSV/Excel) trigger entity extraction. Other files are stored as
    reference documents and embedded for semantic search.
    """
    content = await file.read()
    filename = file.filename or "unknown"
    content_type = (file.content_type or "").lower()

    try:
        result = await ingest.ingest_upload(
            filename,
            content,
            content_type,
            manager=manager,
        )
    except (ValueError, ImportError) as exc:
        raise DomainError(str(exc)) from exc

    doc = result.doc
    response = UploadResponse(
        id=doc.id,
        filename=doc.filename,
        content_type=doc.content_type,
        kind=doc.kind,
        row_count=doc.row_count,
        columns=doc.column_names,
        report_type=result.report_type,
        chunk_count=len(doc.chunks),
        page_count=doc.page_count,
        tags=doc.tags,
        size_bytes=doc.size_bytes,
        knowledge=KnowledgeInfo(
            entities_extracted=result.entities_extracted,
            relationships_extracted=result.relationships_extracted,
            ambiguous_rows=result.ambiguous_rows,
            rows_accepted=result.rows_accepted,
            rows_rejected=result.rows_rejected,
            rows_skipped=result.rows_skipped,
            validation_warnings=result.validation_warnings,
        ),
    )

    try:
        await ws_manager.broadcast("ingestion_complete", {
            "document_id": doc.id,
            "filename": doc.filename,
            "kind": doc.kind,
            "report_type": result.report_type,
            "entities_extracted": result.entities_extracted,
            "chunk_count": len(doc.chunks),
            "tags": doc.tags,
        })
    except Exception:
        _log.warning("broadcast_ingestion_failed", exc_info=True)

    return response


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    q: str | None = Query(default=None, description="Filename search"),
    kind: str | None = Query(default=None, description="Filter by kind: tabular, text, image"),
    tags: str | None = Query(default=None, description="Comma-separated tag filter"),
    sort: str = Query(default="newest", description="Sort: newest, oldest, name"),
    limit: int = Query(default=50, ge=1, le=200),
    ds: DocumentStore = Depends(get_document_store),
) -> DocumentListResponse:
    dk = DocumentKind(kind) if kind else None
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None

    docs = await ds.search_documents(query=q, kind=dk, tags=tag_list, limit=limit)

    if sort == "oldest":
        docs.sort(key=lambda d: d.uploaded_at)
    elif sort == "name":
        docs.sort(key=lambda d: d.filename.lower())

    return DocumentListResponse(documents=[_list_item(d) for d in docs])


@router.get("/tags", response_model=TagsResponse)
async def list_tags(
    ds: DocumentStore = Depends(get_document_store),
) -> TagsResponse:
    """List all tags in use across documents."""
    docs = await ds.list_documents()
    all_tags: set[str] = set()
    for d in docs:
        all_tags.update(d.tags)
    return TagsResponse(tags=sorted(all_tags))


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: str,
    ds: DocumentStore = Depends(get_document_store),
) -> DocumentDetail:
    doc = await ds.get(document_id)
    if doc is None:
        raise NotFoundError("Document", document_id)
    return DocumentDetail(
        id=doc.id,
        filename=doc.filename,
        content_type=doc.content_type,
        kind=doc.kind.value,
        row_count=doc.row_count,
        columns=doc.column_names,
        report_type=doc.metadata.get("report_type", "unknown"),
        chunk_count=len(doc.chunks),
        page_count=doc.page_count,
        tags=doc.tags,
        size_bytes=doc.size_bytes,
        preview=doc.rows[:20],
        uploaded_at=doc.uploaded_at.isoformat(),
    )


@router.get("/{document_id}/rows", response_model=DocumentRowsResponse)
async def query_rows(
    document_id: str,
    limit: int = 100,
    ds: DocumentStore = Depends(get_document_store),
) -> DocumentRowsResponse:
    doc = await ds.get(document_id)
    if doc is None:
        raise NotFoundError("Document", document_id)
    rows = await ds.query_rows(document_id, limit=limit)
    return DocumentRowsResponse(document_id=document_id, rows=rows, count=len(rows))


@router.get("/{document_id}/chunks", response_model=DocumentChunksResponse)
async def query_chunks(
    document_id: str,
    limit: int = 100,
    ds: DocumentStore = Depends(get_document_store),
) -> DocumentChunksResponse:
    """Return text chunks for a text document."""
    doc = await ds.get(document_id)
    if doc is None:
        raise NotFoundError("Document", document_id)
    chunks = [
        ChunkItem(index=c.index, text=c.text, page=c.page)
        for c in doc.chunks[:limit]
    ]
    return DocumentChunksResponse(document_id=document_id, chunks=chunks, count=len(chunks))


@router.patch("/{document_id}/tags", response_model=TagsResponse)
async def update_tags(
    document_id: str,
    body: TagUpdateRequest = Body(...),
    ds: DocumentStore = Depends(get_document_store),
) -> TagsResponse:
    """Update tags for a document."""
    updated = await ds.update_tags(document_id, body.tags)
    if not updated:
        raise NotFoundError("Document", document_id)
    return TagsResponse(tags=body.tags)


@router.delete("/{document_id}", response_model=DeleteResponse)
async def delete_document(
    document_id: str,
    ds: DocumentStore = Depends(get_document_store),
) -> DeleteResponse:
    deleted = await ds.delete(document_id)
    if not deleted:
        raise NotFoundError("Document", document_id)
    return DeleteResponse(deleted=True, id=document_id)
