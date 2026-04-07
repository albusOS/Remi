"""System — agents, documents, usage, realtime.

Platform capabilities: agent chat, document ingestion, LLM usage
tracking, and WebSocket event broadcasting.
"""

from remi.application.api.system.agents import router as agents_router
from remi.application.api.system.documents import router as documents_router
from remi.application.api.system.realtime import router as realtime_router
from remi.application.api.system.usage import router as usage_router

__all__ = [
    "agents_router",
    "documents_router",
    "realtime_router",
    "usage_router",
]
