"""Portfolio CLI subcommands."""

from __future__ import annotations

import asyncio
import json

import typer

cli_group = typer.Typer(name="portfolio", help="Portfolio queries — managers, properties, rent-roll.")


def _run(coro):  # noqa: ANN001, ANN202
    """Tiny async runner for CLI commands."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _container():  # noqa: ANN202
    from remi.shell.config.container import Container

    return Container()


@cli_group.command()
def managers(
    as_json: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """List managers with portfolio metrics."""
    c = _container()
    _run(c.ensure_bootstrapped())
    result = _run(c.manager_resolver.list_managers())
    if as_json:
        typer.echo(json.dumps([m.model_dump() for m in result], default=str, indent=2))
        return
    for m in result:
        typer.echo(f"  {m.name:<30} {m.property_count} props  occ={m.metrics.occupancy_rate:.0%}")


@cli_group.command()
def properties(
    manager_id: str | None = typer.Option(None, help="Filter by manager ID"),
    as_json: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """List properties."""
    c = _container()
    _run(c.ensure_bootstrapped())
    result = _run(c.property_resolver.list_properties(manager_id=manager_id))
    if as_json:
        typer.echo(json.dumps([p.model_dump() for p in result.items], default=str, indent=2))
        return
    for p in result.items:
        typer.echo(f"  {p.name:<40} {p.unit_count} units")


@cli_group.command(name="rent-roll")
def rent_roll(
    property_id: str = typer.Argument(help="Property ID"),
    as_json: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """Show rent roll for a property."""
    c = _container()
    _run(c.ensure_bootstrapped())
    result = _run(c.rent_roll_resolver.get_rent_roll(property_id))
    if as_json:
        typer.echo(json.dumps(result.model_dump(), default=str, indent=2))
        return
    typer.echo(f"Rent roll: {result.property_name} ({len(result.rows)} units)")
    for row in result.rows:
        typer.echo(f"  {row.unit_number:<10} ${row.monthly_rent:>8,.0f}  {row.occupancy_status}")
