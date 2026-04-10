"""Document upload and query REST endpoints — knowledge base API."""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from fastapi import APIRouter, Body, File, Form, Query, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from remi.agent.events import DomainEvent
from remi.agent.tasks import TaskConstraints, TaskSpec
from remi.agent.tasks.task import TaskStatus
from remi.application.core.models import Document
from remi.application.dependencies import Ctr
from remi.application.ingestion.models import (
    ChunkItem,
    DeleteResponse,
    DocumentChunksResponse,
    DocumentDetail,
    DocumentListItem,
    DocumentListResponse,
    DocumentRowsResponse,
    DuplicateInfo,
    KnowledgeInfo,
    ReviewItemSchema,
    ReviewOptionSchema,
    TagsResponse,
    TagUpdateRequest,
    UploadResponse,
)
from remi.types.errors import DomainError, NotFoundError

_log = structlog.get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


def _review_items_to_schemas(
    items: list[object],
) -> list[ReviewItemSchema]:
    """Convert internal ReviewItem dataclasses to API schemas."""
    return [
        ReviewItemSchema(
            kind=ri.kind,  # type: ignore[attr-defined]
            severity=ri.severity,  # type: ignore[attr-defined]
            message=ri.message,  # type: ignore[attr-defined]
            row_index=ri.row_index,  # type: ignore[attr-defined]
            entity_type=ri.entity_type,  # type: ignore[attr-defined]
            entity_id=ri.entity_id,  # type: ignore[attr-defined]
            field_name=ri.field_name,  # type: ignore[attr-defined]
            raw_value=ri.raw_value,  # type: ignore[attr-defined]
            suggestion=ri.suggestion,  # type: ignore[attr-defined]
            options=[
                ReviewOptionSchema(id=o.id, label=o.label)
                for o in ri.options  # type: ignore[attr-defined]
            ],
            row_data=ri.row_data,  # type: ignore[attr-defined]
        )
        for ri in items
    ]


def _list_item(doc: Document) -> DocumentListItem:
    return DocumentListItem(
        id=doc.id,
        filename=doc.filename,
        content_type=doc.content_type,
        kind=doc.kind,
        row_count=doc.row_count,
        columns=[],
        report_type=doc.report_type,
        chunk_count=doc.chunk_count,
        page_count=doc.page_count,
        tags=doc.tags,
        size_bytes=doc.size_bytes,
        uploaded_at=doc.uploaded_at.isoformat(),
    )


def _dispatch_ingestion(c: Ctr, doc_id: str) -> None:
    """Submit an ingestion task to the agent OS via the task supervisor.

    Fire-and-forget from the caller's perspective — the upload response
    returns before ingestion starts.  Failures are logged and published
    to the event bus so frontends can show errors.
    """
    spec = TaskSpec(
        agent_name="ingester",
        objective=f"Ingest document {doc_id}: classify, extract entities, finalize.",
        input_data={"document_id": doc_id},
        constraints=TaskConstraints(timeout_seconds=180, max_tool_rounds=12),
        metadata={"source": "upload_api", "document_id": doc_id},
    )

    async def _publish_and_spawn() -> None:
        try:
            await c.event_bus.publish(
                DomainEvent(
                    topic="ingestion.started",
                    source="upload_api",
                    payload={"document_id": doc_id},
                )
            )
        except Exception:
            _log.warning("event_publish_failed", topic="ingestion.started", exc_info=True)
        await c.task_supervisor.spawn(spec)

    bg = asyncio.create_task(_publish_and_spawn(), name=f"ingest:{doc_id}")
    bg.add_done_callback(lambda t: _on_dispatch_done(t, doc_id))


def _on_dispatch_done(task: "asyncio.Task[None]", doc_id: str) -> None:
    """Log any unhandled error from the background dispatch task."""
    if task.cancelled():
        _log.warning("ingestion_dispatch_cancelled", document_id=doc_id)
        return
    exc = task.exception()
    if exc is not None:
        _log.error(
            "ingestion_dispatch_failed",
            document_id=doc_id,
            error=str(exc),
            exc_info=(type(exc), exc, exc.__traceback__),
        )


@router.post("/upload", response_model=UploadResponse, status_code=202)
async def upload_document(
    c: Ctr,
    file: UploadFile = File(...),
    manager: str | None = Form(default=None),
    unit_id: str | None = Form(default=None),
    property_id: str | None = Form(default=None),
    lease_id: str | None = Form(default=None),
    document_type: str | None = Form(default=None),
) -> UploadResponse | JSONResponse:
    """Upload a file to the knowledge base.

    Returns 202 Accepted immediately. For tabular files, dispatches an
    ingestion task to the agent OS — the ingester agent handles entity
    extraction. Progress is pushed via EventBus (``ingestion.started``,
    ``ingestion.complete``).
    """
    raw_content = await file.read()
    filename = file.filename or "unknown"
    content_type = (file.content_type or "").lower()

    try:
        result = await c.document_ingest.ingest_upload(
            filename,
            raw_content,
            content_type,
            manager=manager,
            unit_id=unit_id,
            property_id=property_id,
            lease_id=lease_id,
            document_type=document_type,
        )
    except (ValueError, ImportError) as exc:
        raise DomainError(str(exc)) from exc

    doc = result.doc

    if result.status == "processing":
        _dispatch_ingestion(c, doc.id)

    review_schemas = _review_items_to_schemas(result.review_items)

    dup_info: DuplicateInfo | None = None
    if result.duplicate_of is not None:
        dup_info = DuplicateInfo(
            existing_id=result.duplicate_of.id,
            existing_filename=result.duplicate_of.filename,
            uploaded_at=result.duplicate_of.uploaded_at.isoformat(),
        )

    warning_strs = [
        f"row {w.row_index} ({w.row_type}).{w.field}: {w.issue}"
        if hasattr(w, "row_index")
        else str(w)
        for w in result.validation_warnings
    ]

    return UploadResponse(
        id=doc.id,
        filename=doc.filename,
        content_type=doc.content_type,
        kind=doc.kind,
        row_count=doc.row_count,
        columns=[],
        report_type=result.report_type,
        status=result.status,
        chunk_count=doc.chunk_count,
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
            observations_captured=result.observations_captured,
            validation_warnings=warning_strs,
            review_items=review_schemas,
        ),
        duplicate=dup_info,
    )


class HumanQuestionOptionSchema(BaseModel):
    id: str
    label: str


class HumanQuestionSchema(BaseModel):
    id: str
    prompt: str
    kind: str
    options: list[HumanQuestionOptionSchema]
    default: str | None
    required: bool


class WaitingTaskResponse(BaseModel):
    status: str
    task_id: str | None = None
    questions: list[HumanQuestionSchema] = []


@router.get("/tasks/waiting", response_model=WaitingTaskResponse)
async def get_waiting_task(
    c: Ctr,
    document_id: str = Query(..., description="Document ID to check for a pending human question"),
) -> WaitingTaskResponse:
    """Return the task waiting on human input for a given document, if any.

    The frontend polls this after uploading a file with ``status: processing``
    to discover whether the ingester has paused with a question.
    Returns ``{"status": "waiting_on_human", "task_id": "...", "questions": [...]}``
    when paused, or ``{"status": "running"}`` / ``{"status": "done"}`` otherwise.
    """
    tasks = c.task_supervisor.list_tasks(status=TaskStatus.WAITING_ON_HUMAN)
    for task in tasks:
        if task.spec.metadata.get("document_id") == document_id:
            questions = [
                HumanQuestionSchema(
                    id=q.id,
                    prompt=q.prompt,
                    kind=q.kind,
                    options=[HumanQuestionOptionSchema(id=o.id, label=o.label) for o in q.options],
                    default=q.default,
                    required=q.required,
                )
                for q in task.human_questions
            ]
            return WaitingTaskResponse(
                status="waiting_on_human",
                task_id=task.id,
                questions=questions,
            )

    all_tasks = c.task_supervisor.list_tasks()
    for task in all_tasks:
        if task.spec.metadata.get("document_id") == document_id:
            if task.is_terminal:
                return WaitingTaskResponse(status="done")
            return WaitingTaskResponse(status="running")

    return WaitingTaskResponse(status="unknown")


class HumanAnswerRequest(BaseModel):
    """Payload for supplying answers to a task.waiting_on_human question."""

    task_id: str
    answers: dict[str, Any]


class HumanAnswerResponse(BaseModel):
    task_id: str
    resumed: bool


@router.post("/tasks/answer", response_model=HumanAnswerResponse)
async def supply_human_answer(
    c: Ctr,
    body: HumanAnswerRequest = Body(...),
) -> HumanAnswerResponse | JSONResponse:
    """Supply answers to a task that is waiting on human input.

    The frontend calls this when the user answers questions posed by
    the ``ask_human`` tool during ingestion or any other agent task.
    """
    resumed = await c.task_supervisor.supply_human_answers(
        body.task_id, body.answers,
    )
    if not resumed:
        return JSONResponse(
            status_code=404,
            content={"detail": f"Task {body.task_id} not found or not waiting on human input"},
        )
    return HumanAnswerResponse(task_id=body.task_id, resumed=True)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    c: Ctr,
    q: str | None = Query(default=None, description="Filename search"),
    kind: str | None = Query(default=None, description="Filter by kind: tabular, text, image"),
    tags: str | None = Query(default=None, description="Comma-separated tag filter"),
    unit_id: str | None = Query(default=None, description="Filter by unit"),
    property_id: str | None = Query(default=None, description="Filter by property"),
    manager_id: str | None = Query(default=None, description="Filter by manager"),
    sort: str = Query(default="newest", description="Sort: newest, oldest, name"),
    limit: int = Query(default=50, ge=1, le=200),
) -> DocumentListResponse:
    docs = await c.property_store.list_documents(
        unit_id=unit_id,
        property_id=property_id,
        manager_id=manager_id,
    )
    if kind:
        docs = [d for d in docs if d.kind == kind]
    if tags:
        tag_set = {t.strip() for t in tags.split(",") if t.strip()}
        docs = [d for d in docs if tag_set & set(d.tags)]
    if q:
        ql = q.lower()
        docs = [d for d in docs if ql in d.filename.lower()]
    if sort == "oldest":
        docs.sort(key=lambda d: d.uploaded_at)
    elif sort == "name":
        docs.sort(key=lambda d: d.filename.lower())
    else:
        docs.sort(key=lambda d: d.uploaded_at, reverse=True)
    return DocumentListResponse(documents=[_list_item(d) for d in docs[:limit]])


@router.get("/tags", response_model=TagsResponse)
async def list_tags(c: Ctr) -> TagsResponse:
    """List all tags in use across documents."""
    docs = await c.property_store.list_documents()
    all_tags: set[str] = set()
    for d in docs:
        all_tags.update(d.tags)
    return TagsResponse(tags=sorted(all_tags))


@router.get("/{document_id}", response_model=DocumentDetail)
async def get_document(
    document_id: str,
    c: Ctr,
) -> DocumentDetail:
    doc = await c.property_store.get_document(document_id)
    if doc is None:
        raise NotFoundError("Document", document_id)
    content = await c.content_store.get(document_id)
    preview = content.rows[:20] if content else []
    columns = content.column_names if content else []
    return DocumentDetail(
        id=doc.id,
        filename=doc.filename,
        content_type=doc.content_type,
        kind=doc.kind,
        row_count=doc.row_count,
        columns=columns,
        report_type=doc.report_type,
        chunk_count=doc.chunk_count,
        page_count=doc.page_count,
        tags=doc.tags,
        size_bytes=doc.size_bytes,
        preview=preview,
        uploaded_at=doc.uploaded_at.isoformat(),
    )


@router.get("/{document_id}/rows", response_model=DocumentRowsResponse)
async def query_rows(
    document_id: str,
    c: Ctr,
    limit: int = 100,
) -> DocumentRowsResponse:
    content = await c.content_store.get(document_id)
    if content is None:
        raise NotFoundError("Document", document_id)
    rows = await c.content_store.query_rows(document_id, limit=limit)
    return DocumentRowsResponse(document_id=document_id, rows=rows, count=len(rows))


@router.get("/{document_id}/chunks", response_model=DocumentChunksResponse)
async def query_chunks(
    document_id: str,
    c: Ctr,
    limit: int = 100,
) -> DocumentChunksResponse:
    """Return text chunks for a text document."""
    content = await c.content_store.get(document_id)
    if content is None:
        raise NotFoundError("Document", document_id)
    chunks = [
        ChunkItem(index=c_chunk.index, text=c_chunk.text, page=c_chunk.page)
        for c_chunk in content.chunks[:limit]
    ]
    return DocumentChunksResponse(document_id=document_id, chunks=chunks, count=len(chunks))


@router.patch("/{document_id}/tags", response_model=TagsResponse)
async def update_tags(
    document_id: str,
    c: Ctr,
    body: TagUpdateRequest = Body(...),
) -> TagsResponse:
    """Update tags for a document."""
    updated = await c.content_store.update_tags(document_id, body.tags)
    if not updated:
        raise NotFoundError("Document", document_id)
    return TagsResponse(tags=body.tags)


@router.delete("/{document_id}", response_model=DeleteResponse)
async def delete_document(
    document_id: str,
    c: Ctr,
) -> DeleteResponse:
    deleted = await c.content_store.delete(document_id)
    if not deleted:
        raise NotFoundError("Document", document_id)
    await c.property_store.delete_document(document_id)
    return DeleteResponse(deleted=True, id=document_id)


# ---------------------------------------------------------------------------
# Format registry endpoints
# ---------------------------------------------------------------------------


class FormatListItem(BaseModel):
    id: str
    manager_id: str
    report_type: str
    column_signature: str
    primary_entity_type: str
    confirmed_by_human: bool
    use_count: int
    last_used: str


class FormatListResponse(BaseModel):
    formats: list[FormatListItem]


@router.get("/formats", response_model=FormatListResponse)
async def list_formats(
    c: Ctr,
    manager_id: str | None = Query(default=None),
    confirmed_only: bool = Query(default=False),
) -> FormatListResponse:
    """List known ingestion formats from the registry."""
    formats = await c.format_registry.list_all(
        manager_id=manager_id,
        confirmed_only=confirmed_only,
    )
    items = [
        FormatListItem(
            id=f.id,
            manager_id=f.manager_id,
            report_type=f.report_type,
            column_signature=f.column_signature,
            primary_entity_type=f.primary_entity_type,
            confirmed_by_human=f.confirmed_by_human,
            use_count=f.use_count,
            last_used=f.last_used.isoformat(),
        )
        for f in formats
    ]
    return FormatListResponse(formats=items)
