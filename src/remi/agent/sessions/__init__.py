"""Chat session persistence — factory and adapters.

Public API::

    from remi.agent.sessions import build_chat_session_store
    from remi.agent.sessions import InMemoryChatSessionStore
"""

from remi.agent.sessions.factory import build_chat_session_store
from remi.agent.sessions.mem import InMemoryChatSessionStore

__all__ = [
    "build_chat_session_store",
    "InMemoryChatSessionStore",
]
