"""Ingestion CLI — document upload and status."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer

cli_group = typer.Typer(name="ingestion", help="Document ingestion commands.")


def _container():
    from remi.shell.config.container import Container
    return Container()


@cli_group.command()
def upload(
    file: Path = typer.Argument(help="Path to document file"),
    manager: str | None = typer.Option(None, help="Manager name or ID"),
    property_id: str | None = typer.Option(None, help="Property ID"),
    document_type: str | None = typer.Option(None, help="Document type hint"),
) -> None:
    """Upload and ingest a document."""
    if not file.exists():
        typer.echo(f"File not found: {file}", err=True)
        raise typer.Exit(code=1)

    content = file.read_bytes()
    content_type = _guess_content_type(file)

    c = _container()
    result = asyncio.run(
        c.document_ingest.ingest_upload(
            filename=file.name,
            content=content,
            content_type=content_type,
            manager=manager,
            property_id=property_id,
            document_type=document_type,
        )
    )
    typer.echo(json.dumps(result.model_dump(mode="json"), indent=2, default=str))


@cli_group.command()
def documents(
    output: str = typer.Option("json", help="Output format: json"),
) -> None:
    """List ingested documents."""
    c = _container()
    docs = asyncio.run(c.content_store.list_documents())

    if not docs:
        typer.echo("No documents found.")
        return
    typer.echo(json.dumps([d.model_dump(mode="json") for d in docs], indent=2, default=str))


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
