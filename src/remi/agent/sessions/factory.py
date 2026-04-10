"""Chat session store factory — backend selection based on settings."""

from __future__ import annotations

from pydantic import BaseModel

from remi.agent.sessions.mem import InMemoryChatSessionStore
from remi.agent.types import ChatSessionStore


class SessionStoreSettings(BaseModel):
    """Chat session persistence — ``memory`` or ``postgres``."""

    backend: str = "memory"


def build_chat_session_store(settings: SessionStoreSettings) -> ChatSessionStore:
    """Return a ChatSessionStore for the configured backend.

    Currently supports ``memory``.  The ``postgres`` branch will be
    added when ``agent.sessions.pg`` is implemented.
    """
    backend = settings.backend
    if backend == "memory":
        return InMemoryChatSessionStore()

    raise ValueError(f"Unknown sessions.backend: {backend!r}")
