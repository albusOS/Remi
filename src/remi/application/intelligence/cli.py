"""Intelligence CLI subcommands."""

from __future__ import annotations

import asyncio
import json

import typer

cli_group = typer.Typer(name="intelligence", help="Intelligence queries — dashboard, search.")


def _run(coro):  # noqa: ANN001, ANN202
    return asyncio.get_event_loop().run_until_complete(coro)


def _container():  # noqa: ANN202
    from remi.shell.config.container import Container

    return Container()


@cli_group.command()
def dashboard(
    as_json: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """Show portfolio dashboard overview."""
    c = _container()
    _run(c.ensure_bootstrapped())
    result = _run(c.dashboard_resolver.get_overview())
    if as_json:
        typer.echo(json.dumps(result.model_dump(), default=str, indent=2))
        return
    typer.echo(f"Portfolio: {result.total_properties} properties, "
               f"{result.total_units} units, "
               f"occupancy {result.occupancy_rate:.0%}")


@cli_group.command()
def search(
    query: str = typer.Argument(help="Search query"),
    as_json: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """Search entities by name or address."""
    c = _container()
    _run(c.ensure_bootstrapped())
    results = _run(c.search_service.search(query))
    if as_json:
        typer.echo(json.dumps([r.model_dump() for r in results], default=str, indent=2))
        return
    for r in results:
        typer.echo(f"  [{r.entity_type}] {r.name}  (score={r.score:.2f})")
