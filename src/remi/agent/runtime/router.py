"""Request router — classifies user questions into execution tiers.

Three tiers, cheapest first:

- **direct**: Conversation, greetings, follow-ups. Single LLM call,
  no data fetch, no tools.
- **query**: Data questions answerable by a known resolver operation.
  Data is fetched in-process, injected into a single LLM call.
  Zero tool calls.
- **agent**: Complex, open-ended work.  Full agent loop with sandbox,
  CLI, tools, delegation.

This module defines the protocol and tier enum only.  Domain-specific
classification logic lives in the application layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


class Tier(str, Enum):
    """Execution tier — determines the response path."""

    DIRECT = "direct"
    QUERY = "query"
    AGENT = "agent"


@dataclass(frozen=True)
class RoutingDecision:
    """Output of the classifier — what tier and what data to fetch."""

    tier: Tier
    operation: str = ""
    params: dict[str, str] = field(default_factory=dict)
    confidence: float = 1.0


class RequestRouter(Protocol):
    """Protocol for request classifiers.

    Domain-specific implementations live in the application layer.
    The runtime depends only on this protocol.
    """

    def classify(self, question: str, *, manager_id: str | None = None) -> RoutingDecision: ...
