"""Trace store factory — backend selection based on settings."""

from __future__ import annotations

from remi.agent.observe.mem import InMemoryTraceStore
from remi.agent.observe.types import TraceStore
from remi.types.config import RemiSettings


def build_trace_store(settings: RemiSettings) -> TraceStore:
    """Return a TraceStore for the configured backend.

    Currently supports ``memory``.  The ``postgres`` branch will be
    added when ``agent.observe.pg`` is implemented.
    """
    backend = settings.tracing.backend
    if backend == "memory":
        return InMemoryTraceStore()

    raise ValueError(f"Unknown tracing.backend: {backend!r}")
