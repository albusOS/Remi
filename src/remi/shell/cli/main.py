"""CLI mountpoint — registers all slice CLIs. No commands defined here."""

from __future__ import annotations

import typer

# application slice
from remi.shell.cli.agents import ai_cmd
from remi.shell.cli.bench import cmd as bench_cmd
from remi.shell.cli.research import cmd as research_cmd

# domain/intelligence slice
from remi.shell.cli.ontology import cmd as onto_cmd
from remi.shell.cli.search import cmd as search_cmd
from remi.shell.cli.trace import cmd as trace_cmd
from remi.shell.cli.vectors import cmd as vectors_cmd
from remi.shell.cli.documents import cmd as documents_cmd

# domain/portfolio slice
from remi.shell.cli.properties import (
    leases_cmd,
    maintenance_cmd,
    portfolio_cmd,
    property_cmd,
    report_cmd,
    tenants_cmd,
    units_cmd,
)
from remi.shell.cli.seed import cmd as seed_cmd

cli = typer.Typer(
    name="remi",
    help="REMI — Real Estate Management Intelligence.",
    no_args_is_help=True,
)

cli.add_typer(ai_cmd)
cli.add_typer(research_cmd)
cli.add_typer(portfolio_cmd)
cli.add_typer(property_cmd)
cli.add_typer(units_cmd)
cli.add_typer(leases_cmd)
cli.add_typer(maintenance_cmd)
cli.add_typer(tenants_cmd)
cli.add_typer(report_cmd)
cli.add_typer(documents_cmd)
cli.add_typer(onto_cmd)
cli.add_typer(search_cmd)
cli.add_typer(seed_cmd)
cli.add_typer(trace_cmd)
cli.add_typer(vectors_cmd)
cli.add_typer(bench_cmd)


@cli.command()
def dashboard(
    agent: str = typer.Option("director", "--agent", "-a", help="Agent to chat with"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show LLM token deltas"),
) -> None:
    """Open the live portfolio dashboard (Textual TUI)."""
    try:
        from remi.shell.cli.dashboard import run as run_dashboard
    except ImportError as exc:
        typer.echo(f"Dashboard requires textual: {exc}", err=True)
        raise typer.Exit(1) from exc
    run_dashboard(agent=agent, verbose=verbose)


@cli.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to listen on"),
    reload: bool = typer.Option(False, help="Enable auto-reload"),
    seed: bool = typer.Option(False, "--seed", help="Ingest AppFolio reports at startup"),
) -> None:
    """Start the API server."""
    import os

    import uvicorn

    from remi.shell.cli.banner import print_banner

    if seed:
        os.environ["REMI_SEED"] = "1"

    print_banner(host=host, port=port, reload=reload, seed=seed)

    uvicorn.run(
        "remi.shell.api.main:app",
        host=host,
        port=port,
        reload=reload,
    )


app = cli
