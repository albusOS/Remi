"""Operations CLI subcommands."""

from __future__ import annotations

import asyncio
import json

import typer

cli_group = typer.Typer(name="operations", help="Operations queries — leases, maintenance.")


def _run(coro):  # noqa: ANN001, ANN202
    return asyncio.get_event_loop().run_until_complete(coro)


def _container():  # noqa: ANN202
    from remi.shell.config.container import Container

    return Container()


@cli_group.command()
def leases(
    property_id: str | None = typer.Option(None, help="Filter by property ID"),
    status: str | None = typer.Option(None, help="Filter by status"),
    as_json: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """List leases."""
    c = _container()
    _run(c.ensure_bootstrapped())
    result = _run(c.lease_resolver.list_leases(property_id=property_id, status=status))
    if as_json:
        typer.echo(json.dumps(result.model_dump(), default=str, indent=2))
        return
    typer.echo(f"Leases: {result.total}")
    for le in result.items:
        typer.echo(f"  {le.tenant:<30} ${le.rent:>8,.0f}  {le.status}")


@cli_group.command()
def maintenance(
    property_id: str | None = typer.Option(None, help="Filter by property ID"),
    as_json: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """List maintenance requests."""
    c = _container()
    _run(c.ensure_bootstrapped())
    result = _run(c.maintenance_resolver.list_requests(property_id=property_id))
    if as_json:
        typer.echo(json.dumps(result.model_dump(), default=str, indent=2))
        return
    typer.echo(f"Maintenance requests: {result.total}")
    for req in result.items:
        typer.echo(f"  {req.title:<40} {req.status}  {req.priority}")
