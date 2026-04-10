"""Ingestion CLI — document upload, listing, and search."""

from __future__ import annotations

import asyncio
from pathlib import Path

import structlog
import typer

from remi.application.cli_output import emit_error, emit_success

_log = structlog.get_logger(__name__)

cli_group = typer.Typer(name="ingestion", help="Document ingestion commands.")


def _is_remote() -> bool:
    from remi.shell.cli.client import get_api_url

    return get_api_url() is not None


def _container():  # noqa: ANN202
    from remi.shell.config.container import Container

    return Container()


def _guess_content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".csv": "text/csv",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
        ".pdf": "application/pdf",
        ".txt": "text/plain",
        ".json": "application/json",
    }.get(suffix, "application/octet-stream")


@cli_group.command()
def upload(
    file: Path = typer.Argument(help="Path to document file"),
    manager: str | None = typer.Option(None, help="Manager name or ID"),
    property_id: str | None = typer.Option(None, help="Property ID"),
    document_type: str | None = typer.Option(None, help="Document type hint"),
) -> None:
    """Upload and ingest a document."""
    if not file.exists():
        emit_error(
            "FILE_NOT_FOUND",
            f"File not found: {file}",
            command="remi ingestion upload",
        )
        raise typer.Exit(1)

    content = file.read_bytes()
    content_type = _guess_content_type(file)

    if _is_remote():
        from remi.shell.cli.client import post_file

        fields: dict[str, str] = {}
        if manager:
            fields["manager"] = manager
        if property_id:
            fields["property_id"] = property_id
        if document_type:
            fields["document_type"] = document_type

        data = post_file(
            "/documents/upload",
            filepath=file.name,
            file_bytes=content,
            content_type=content_type,
            fields=fields,
        )
        emit_success(data, command="remi ingestion upload")
        return

    c = _container()

    async def _run() -> dict[str, object]:
        await c.ensure_bootstrapped()
        result = await c.document_ingest.ingest_upload(
            filename=file.name,
            content=content,
            content_type=content_type,
            manager=manager,
            property_id=property_id,
            document_type=document_type,
        )
        if result.status == "processing":
            from remi.agent.tasks import TaskConstraints, TaskSpec

            spec = TaskSpec(
                agent_name="ingester",
                objective=f"Ingest document {result.doc.id}: classify, extract entities, finalize.",
                input_data={"document_id": result.doc.id},
                constraints=TaskConstraints(timeout_seconds=120, max_tool_rounds=6),
                metadata={"source": "cli_upload", "document_id": result.doc.id},
            )
            task_result = await c.task_supervisor.spawn_and_wait(spec)
            if not task_result.ok:
                _log.warning(
                    "cli_ingestion_failed",
                    doc_id=result.doc.id,
                    error=task_result.error,
                )
        return {
            "id": result.doc.id,
            "filename": result.doc.filename,
            "status": result.status,
            "report_type": result.report_type,
        }

    data = asyncio.run(_run())
    emit_success(data, command="remi ingestion upload")


@cli_group.command()
def documents(
    manager_id: str | None = typer.Option(None, help="Filter by manager ID"),
    property_id: str | None = typer.Option(None, help="Filter by property ID"),
) -> None:
    """List ingested documents."""
    if _is_remote():
        from remi.shell.cli.client import get

        params: dict[str, str] = {}
        if manager_id:
            params["manager_id"] = manager_id
        if property_id:
            params["property_id"] = property_id
        data = get("/documents", params=params or None)
        emit_success(
            data.get("documents", data),
            command="remi ingestion documents",
        )
        return

    c = _container()
    if manager_id or property_id:
        docs = asyncio.run(
            c.property_store.list_documents(
                manager_id=manager_id,
                property_id=property_id,
            )
        )
    else:
        docs = asyncio.run(c.content_store.list_documents())

    emit_success(
        [d.model_dump(mode="json") for d in docs] if docs else [],
        command="remi ingestion documents",
    )


@cli_group.command(name="document-search")
def document_search(
    query: str = typer.Argument(help="Search query"),
    property_id: str | None = typer.Option(None, help="Filter by property"),
    limit: int = typer.Option(10, help="Max results"),
) -> None:
    """Semantic search across document content."""
    if _is_remote():
        from remi.shell.cli.client import get

        params: dict[str, str] = {"q": query}
        if property_id:
            params["property_id"] = property_id
        data = get("/search", params=params)
        results = data.get("results", data)
        emit_success(results, command="remi ingestion document-search")
        return

    c = _container()
    results = asyncio.run(c.search_service.search(query))
    emit_success(
        [r.model_dump(mode="json") for r in results],
        command="remi ingestion document-search",
    )
