"""remi research — deep analytical question on the portfolio.

Runs the director agent in agent mode with a single-shot question.
Use for ad-hoc analytical queries from the command line.
"""

from __future__ import annotations

import asyncio

import typer

from remi.application.cli.shared import get_container_async, use_json

cmd = typer.Typer(
    name="research",
    help="Run deep portfolio analysis via the director agent.",
    no_args_is_help=True,
)


@cmd.callback(invoke_without_command=True)
def research(
    question: str = typer.Argument(
        ...,
        help="Research question or directive",
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show LLM output live"),
) -> None:
    """Run a deep research analysis on the portfolio."""
    asyncio.run(_run_research(question, use_json(json_output), verbose))


async def _run_research(question: str, fmt_json: bool, verbose: bool) -> None:
    from remi.application.cli.intelligence.agent_runner import run_single_shot

    container = await get_container_async()
    await run_single_shot(
        container,
        "director",
        question,
        "agent",
        fmt_json=fmt_json,
        verbose=verbose,
    )
