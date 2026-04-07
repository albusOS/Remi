"""CLI entrypoint — ``remi serve`` plus auto-discovered capability subcommands."""

from __future__ import annotations

import typer

from remi.shell.config.capabilities import (
    all_capabilities,
    ensure_capabilities_registered,
    resolve_cli_group,
)

cli = typer.Typer(
    name="remi",
    help="REMI — Real Estate Management Intelligence.",
    no_args_is_help=True,
)


@cli.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to listen on"),
    reload: bool = typer.Option(False, help="Enable auto-reload"),
) -> None:
    """Start the API server."""
    import uvicorn

    uvicorn.run(
        "remi.shell.api.main:app",
        host=host,
        port=port,
        reload=reload,
    )


ensure_capabilities_registered()

for _cap in all_capabilities().values():
    _group = resolve_cli_group(_cap)
    if _group is not None:
        cli.add_typer(_group, name=_cap.name)

app = cli
