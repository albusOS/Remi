"""REST endpoints for entailed signals."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends

from remi.agent.signals import FeedbackStore, Signal, SignalStore
from remi.application.api.dependencies import (
    get_feedback_store,
    get_signal_store,
)

_log = structlog.get_logger(__name__)
from remi.application.api.intelligence.signal_schemas import (
    FeedbackListResponse,
    FeedbackRequest,
    FeedbackResponse,
    SignalDetailResponse,
    SignalExplainResponse,
    SignalListResponse,
    SignalSummary,
)
from remi.types.errors import NotFoundError

router = APIRouter(prefix="/signals", tags=["signals"])


def _signal_summary(s: Signal) -> SignalSummary:
    return SignalSummary(
        signal_id=s.signal_id,
        signal_type=s.signal_type,
        severity=s.severity.value,
        entity_type=s.entity_type,
        entity_id=s.entity_id,
        entity_name=s.entity_name,
        description=s.description,
        detected_at=s.detected_at.isoformat(),
    )


@router.get("")
async def list_signals(
    manager_id: str | None = None,
    property_id: str | None = None,
    severity: str | None = None,
    signal_type: str | None = None,
    ss: SignalStore = Depends(get_signal_store),
) -> SignalListResponse:
    scope: dict[str, str] | None = None
    if manager_id or property_id:
        scope = {}
        if manager_id:
            scope["manager_id"] = manager_id
        if property_id:
            scope["property_id"] = property_id
    signals = await ss.list_signals(
        scope=scope,
        severity=severity,
        signal_type=signal_type,
    )
    return SignalListResponse(
        count=len(signals),
        signals=[_signal_summary(s) for s in signals],
    )


@router.get("/digest")
async def signal_digest(
    ss: SignalStore = Depends(get_signal_store),
) -> dict[str, Any]:
    """Grouped signal briefing for the frontend home screen.

    Groups all active signals by entity, sorted by severity, with
    counts per severity level. Designed for the "situation feed" UI.
    """
    from collections import defaultdict

    all_signals = await ss.list_signals()

    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    by_entity: dict[str, list[Signal]] = defaultdict(list)
    for s in all_signals:
        by_entity[s.entity_id].append(s)

    groups: list[dict[str, Any]] = []
    for entity_id, sigs in by_entity.items():
        sigs.sort(key=lambda s: severity_rank.get(s.severity.value, 99))
        worst = sigs[0]

        severity_counts: dict[str, int] = defaultdict(int)
        for s in sigs:
            severity_counts[s.severity.value] += 1

        groups.append({
            "entity_id": entity_id,
            "entity_type": worst.entity_type,
            "entity_name": worst.entity_name,
            "worst_severity": worst.severity.value,
            "signal_count": len(sigs),
            "severity_counts": dict(severity_counts),
            "signals": [_signal_summary(s).model_dump(mode="json") for s in sigs],
        })

    groups.sort(key=lambda g: severity_rank.get(g["worst_severity"], 99))

    total_by_severity: dict[str, int] = defaultdict(int)
    for s in all_signals:
        total_by_severity[s.severity.value] += 1

    return {
        "total_signals": len(all_signals),
        "total_entities": len(groups),
        "severity_counts": dict(total_by_severity),
        "entities": groups,
    }


@router.get("/{signal_id}")
async def get_signal(
    signal_id: str,
    ss: SignalStore = Depends(get_signal_store),
) -> SignalDetailResponse:
    signal = await ss.get_signal(signal_id)
    if signal is None:
        raise NotFoundError("Signal", signal_id)
    return SignalDetailResponse(
        **_signal_summary(signal).model_dump(),
    )


@router.get("/{signal_id}/explain")
async def explain_signal(
    signal_id: str,
    ss: SignalStore = Depends(get_signal_store),
) -> SignalExplainResponse:
    signal = await ss.get_signal(signal_id)
    if signal is None:
        raise NotFoundError("Signal", signal_id)
    return SignalExplainResponse(
        **_signal_summary(signal).model_dump(),
        provenance=signal.provenance.value,
        evidence=signal.evidence,
    )


@router.post("/{signal_id}/feedback")
async def record_feedback(
    signal_id: str,
    body: FeedbackRequest,
    ss: SignalStore = Depends(get_signal_store),
    fs: FeedbackStore = Depends(get_feedback_store),
) -> FeedbackResponse:
    """Record feedback on a signal."""
    import uuid

    from remi.agent.signals import SignalFeedback, SignalOutcome

    signal = await ss.get_signal(signal_id)
    if signal is None:
        raise NotFoundError("Signal", signal_id)

    outcome = SignalOutcome(body.outcome)
    feedback = SignalFeedback(
        feedback_id=f"fb-{uuid.uuid4().hex[:12]}",
        signal_id=signal_id,
        signal_type=signal.signal_type,
        outcome=outcome,
        actor=body.actor,
        notes=body.notes,
        context=body.context,
    )
    await fs.record_feedback(feedback)
    return FeedbackResponse(
        feedback_id=feedback.feedback_id,
        signal_id=signal_id,
        outcome=outcome.value,
    )


@router.get("/{signal_id}/feedback")
async def list_signal_feedback(
    signal_id: str,
    fs: FeedbackStore = Depends(get_feedback_store),
) -> FeedbackListResponse:
    """List feedback events for a specific signal."""
    entries = await fs.list_feedback(
        signal_id=signal_id,
    )
    return FeedbackListResponse(
        signal_id=signal_id,
        count=len(entries),
        feedback=entries,
    )


@router.get("/feedback/summary/{signal_type}")
async def feedback_summary(
    signal_type: str,
    fs: FeedbackStore = Depends(get_feedback_store),
) -> dict[str, Any]:
    """Aggregated feedback stats for a signal type."""
    summary = await fs.summarize(signal_type)
    return summary.model_dump(mode="json")
