"""CLI entrypoint — ``remi serve`` plus auto-discovered capability subcommands."""

from __future__ import annotations

import typer

from remi.agent.observe import configure_logging
from remi.shell.config.capabilities import (
    all_capabilities,
    ensure_capabilities_registered,
    resolve_cli_group,
)

configure_logging(level="WARNING")

cli = typer.Typer(
    name="remi",
    help="REMI — Real Estate Management Intelligence.",
    no_args_is_help=True,
)


@cli.command()
def serve(
    host: str = typer.Option("", help="Host to bind to (default: settings.api.host)"),
    port: int = typer.Option(0, help="Port to listen on (default: settings.api.port)"),
    reload: bool = typer.Option(False, help="Enable auto-reload"),
) -> None:
    """Start the API server."""
    import uvicorn

    from remi.shell.config.settings import load_settings

    settings = load_settings()
    uvicorn.run(
        "remi.shell.api.main:app",
        host=host or settings.api.host,
        port=port or settings.api.port,
        reload=reload,
    )


ensure_capabilities_registered()

for _cap in all_capabilities().values():
    _group = resolve_cli_group(_cap)
    if _group is not None:
        cli.add_typer(_group, name=_cap.name)

app = cli
