"""Agent context — perception, intent classification, and context rendering.

Public API::

    from remi.agent.context import build_context_builder, WorldState
"""

from remi.agent.context.builder import build_context_builder
from remi.agent.context.frame import WorldState

__all__ = [
    "WorldState",
    "build_context_builder",
]
