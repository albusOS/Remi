"""Typed event envelope — the wire format for all events on the bus.

The ``EventBus`` is general-purpose infrastructure.  Three logical
channels share the same bus primitive, distinguished by topic namespace:

- **domain.\*** — world-state transitions (``ingestion.complete``,
  ``entity.updated``).  Durable, buffered, everyone subscribes.
- **agent.\*** — agent lifecycle events (``agent.completed``,
  ``agent.handoff``, ``workspace.updated``).  Session-scoped,
  consumed by orchestrators, peer agents, and optionally the UI.
- **ui.\*** — ephemeral rendering telemetry (``ui.delta``,
  ``ui.tool_call``).  Small buffer, only the active frontend session.

Today only ``domain.*`` is populated; the other namespaces are reserved
for multi-agent orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Immutable, typed event that flows through the EventBus.

    Despite the name, a ``DomainEvent`` is the *envelope* for any event
    on the bus — domain, agent-lifecycle, or UI telemetry.  The ``topic``
    namespace determines the logical channel.

    ``topic`` uses dot-separated namespacing.  Subscribers can register
    for a prefix glob (``"agent.*"``) or an exact match.

    ``payload`` is the event-specific data.  It's typed ``dict[str, Any]``
    here because the bus is a transport layer — producers and consumers
    agree on the schema for each topic via convention and documentation,
    not via the bus itself.
    """

    topic: str
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: uuid4().hex[:16])
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    source: str = ""
