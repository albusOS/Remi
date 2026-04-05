"""Shared agent invocation logic for CLI commands.

Both ``remi ai`` (single-shot) and ``remi research`` share the same
pattern: bootstrap perception, wire the live display, call the agent,
render the result. This module owns that flow.
"""

from __future__ import annotations

from typing import Any

import structlog
import typer

from remi.application.cli.shared import json_out

logger = structlog.get_logger(__name__)


async def run_single_shot(
    container: Any,
    agent_name: str,
    question: str,
    mode: str,
    *,
    fmt_json: bool = False,
    verbose: bool = False,
) -> None:
    """Execute a single-shot agent question with perception + display."""
    from remi.agent.context.frame import WorldState
    from remi.application.cli.intelligence.live_display import LiveAgentDisplay

    world = WorldState.from_tbox(container.domain_tbox)
    perception = await _build_perception(container)

    display: LiveAgentDisplay | None = None
    if not fmt_json:
        display = LiveAgentDisplay(verbose=verbose)
        settings = container.settings
        display.show_start(
            agent_name,
            settings.llm.default_model,
            settings.llm.default_provider,
        )
        display.show_perception(
            tbox_injected=world.loaded,
            signal_count=perception.active_signals,
            severity_breakdown=perception.severity_breakdown,
        )

    on_event = display.on_event if display and not fmt_json else None

    try:
        answer, run_id = await container.chat_agent.ask(
            agent_name,
            question,
            mode=mode,
            on_event=on_event,
        )
    except Exception as exc:
        if fmt_json:
            json_out({"ok": False, "error": str(exc)})
        else:
            typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from None

    if fmt_json:
        json_out({
            "ok": True,
            "agent": agent_name,
            "run_id": run_id,
            "mode": mode,
            "question": question,
            "answer": answer,
            "perception": {**world.to_dict(), **perception.to_dict()},
        })
    else:
        if display:
            from remi.agent.observe import get_current_trace_id
            display.show_done(trace_id=get_current_trace_id())
        if answer:
            typer.echo(f"\n{answer}\n")
        else:
            typer.echo("No response generated.", err=True)
            raise typer.Exit(1)


async def _build_perception(container: Any) -> Any:
    """Build a PerceptionSnapshot from current signal state."""
    from remi.agent.context.frame import PerceptionSnapshot

    try:
        signals = await container.signal_store.list_signals()
        severity_counts: dict[str, int] = {}
        for s in signals:
            sev = s.severity.value if hasattr(s.severity, "value") else str(s.severity)
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
        return PerceptionSnapshot(
            active_signals=len(signals),
            severity_counts=severity_counts,
        )
    except Exception:
        logger.debug("signal_fetch_for_display_failed", exc_info=True)
        return PerceptionSnapshot()
