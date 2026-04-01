"""remi research — deep analytical question on the portfolio.

Runs the director agent in agent mode with a single-shot question.
Use for ad-hoc analytical queries from the command line.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
import typer

logger = structlog.get_logger(__name__)

from remi.cli.shared import get_container_async, json_out, use_json

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
    from remi.cli.live_display import LiveAgentDisplay

    container = await get_container_async()

    display: LiveAgentDisplay | None = None
    if not fmt_json:
        display = LiveAgentDisplay(verbose=verbose)

        signal_count = 0
        severity_breakdown: dict[str, int] = {}
        try:
            signals = await container.signal_store.list_signals()
            signal_count = len(signals)
            for s in signals:
                sev = s.severity.value if hasattr(s.severity, "value") else str(s.severity)
                severity_breakdown[sev] = severity_breakdown.get(sev, 0) + 1
        except Exception:
            logger.debug("signal_fetch_for_display_failed", exc_info=True)

        settings = container.settings
        display.show_start(
            "director",
            settings.llm.default_model,
            settings.llm.default_provider,
        )
        display.show_perception(
            tbox_injected=container.domain_rulebook is not None,
            signal_count=signal_count,
            severity_breakdown=severity_breakdown,
        )

    on_event: Any = None
    if display and not fmt_json:
        on_event = display.on_event

    try:
        answer, run_id = await container.chat_agent.ask(
            "director",
            question,
            mode="agent",
            on_event=on_event,
        )
    except Exception as exc:
        if fmt_json:
            json_out({"ok": False, "error": str(exc)})
        else:
            typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from None

    if fmt_json:
        json_out(
            {
                "ok": True,
                "agent": "director",
                "run_id": run_id,
                "question": question,
                "answer": answer,
            }
        )
    else:
        if display:
            from remi.observability.tracer import get_current_trace_id

            display.show_done(trace_id=get_current_trace_id())
        if answer:
            typer.echo(f"\n{answer}\n")
        else:
            typer.echo("No response generated.", err=True)
            raise typer.Exit(1)
