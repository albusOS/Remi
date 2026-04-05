"""Chat session store factory — backend selection based on settings."""

from __future__ import annotations

from remi.agent.sessions.mem import InMemoryChatSessionStore
from remi.agent.types import ChatSessionStore
from remi.types.config import RemiSettings


def build_chat_session_store(settings: RemiSettings) -> ChatSessionStore:
    """Return a ChatSessionStore for the configured backend.

    Currently supports ``memory``.  The ``postgres`` branch will be
    added when ``agent.sessions.pg`` is implemented.
    """
    backend = settings.sessions.backend
    if backend == "memory":
        return InMemoryChatSessionStore()

    raise ValueError(f"Unknown sessions.backend: {backend!r}")
