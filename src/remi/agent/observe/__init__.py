"""Observability — structured logging, tracing, and usage tracking.

Public API::

    from remi.agent.observe import Tracer, TraceStore, LLMUsageLedger, build_trace_store
"""

from remi.agent.observe.events import Event
from remi.agent.observe.factory import build_trace_store
from remi.agent.observe.logging import configure_logging
from remi.agent.observe.types import Span, SpanKind, Tracer, TraceStore, get_current_trace_id
from remi.agent.observe.usage import LLMUsageLedger, UsageReport, UsageSummary

__all__ = [
    "Event",
    "LLMUsageLedger",
    "Span",
    "SpanKind",
    "Tracer",
    "TraceStore",
    "UsageReport",
    "UsageSummary",
    "build_trace_store",
    "configure_logging",
    "get_current_trace_id",
]
