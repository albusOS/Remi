"""Event feed — projects bus events to external consumers.

Exposes the ``EventBus`` ring buffer as both a pollable HTTP endpoint
(``GET /api/v1/feed``) and a push WebSocket (``WS /api/v1/feed/ws``).

Clients filter by topic glob, so the same endpoints serve all logical
channels (``domain.*``, ``agent.*``, ``ui.*``).  Today only ``domain.*``
events are published; agent lifecycle and UI telemetry topics will be
added when multi-agent orchestration lands.

Agent chat telemetry currently flows through a separate per-session
NDJSON stream on ``POST /agents/{name}/ask`` — it will migrate to
``ui.*`` on the bus when the orchestrator needs to observe it.
"""

__all__: list[str] = []
