"""Trace store factory — backend selection based on settings."""

from __future__ import annotations

from pydantic import BaseModel

from remi.agent.observe.mem import InMemoryTraceStore
from remi.agent.observe.types import TraceStore


class TraceStoreSettings(BaseModel):
    """Trace/span persistence — ``memory`` or ``postgres``."""

    backend: str = "memory"


def build_trace_store(settings: TraceStoreSettings) -> TraceStore:
    """Return a TraceStore for the configured backend.

    Currently supports ``memory``.  The ``postgres`` branch will be
    added when ``agent.observe.pg`` is implemented.
    """
    backend = settings.backend
    if backend == "memory":
        return InMemoryTraceStore()

    raise ValueError(f"Unknown tracing.backend: {backend!r}")
