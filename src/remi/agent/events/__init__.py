"""Event bus — the OS-level typed pub-sub nervous system.

A general-purpose primitive: producers emit typed ``DomainEvent``
payloads on namespaced topics, subscribers react asynchronously.
The bus is a protocol — inner layers define it, the shell wires
the implementation.

Three logical channels share the bus, distinguished by topic namespace:

- ``domain.*`` — world-state transitions (durable, everyone subscribes)
- ``agent.*``  — agent lifecycle events (session-scoped, orchestrators + peers)
- ``ui.*``     — ephemeral rendering telemetry (active frontend only)

Today only ``domain.*`` is populated.  The bus infrastructure is
channel-agnostic by design so multi-agent orchestration can add
``agent.*`` and ``ui.*`` producers without changing the primitive.

The ``EventBuffer`` is a bounded ring buffer that subscribes to the bus
and provides cursor-based polling for HTTP clients.

Public API::

    from remi.agent.events import DomainEvent, EventBus, InMemoryEventBus
    from remi.agent.events import EventBuffer, BufferedEvent
"""

from remi.agent.events.buffer import BufferedEvent, EventBuffer, InMemoryEventBuffer
from remi.agent.events.bus import EventBus, InMemoryEventBus
from remi.agent.events.envelope import DomainEvent
from remi.agent.events.factory import build_event_bus

__all__ = [
    "BufferedEvent",
    "DomainEvent",
    "EventBuffer",
    "EventBus",
    "InMemoryEventBuffer",
    "InMemoryEventBus",
    "build_event_bus",
]
