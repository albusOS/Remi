"""Mutation tools — agent-driven fact assertion and entity context annotation.

These are write operations with side effects (creates Notes, publishes to
EventBus) and are registered as separate tools rather than query operations.

Provides: assert_fact, add_context
"""

from __future__ import annotations

import json
from typing import Any

from remi.agent.events import EventBus
from remi.agent.types import ToolArg, ToolDefinition, ToolProvider, ToolRegistry
from remi.application.core.events import EventStore
from remi.application.core.protocols import PropertyStore
from remi.application.intelligence.assertions import add_context, assert_fact


class MutationToolProvider(ToolProvider):
    """Registers assert_fact and add_context tools."""

    def __init__(
        self,
        *,
        property_store: PropertyStore,
        event_store: EventStore | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._ps = property_store
        self._event_store = event_store
        self._event_bus = event_bus

    def register(self, registry: ToolRegistry) -> None:
        self._register_assert_fact(registry)
        self._register_add_context(registry)

    def _register_assert_fact(self, registry: ToolRegistry) -> None:
        ps = self._ps
        event_store = self._event_store
        event_bus = self._event_bus

        async def _assert_fact(args: dict[str, Any]) -> dict[str, str]:
            props = args.get("properties", {})
            if isinstance(props, str):
                props = json.loads(props)
            return await assert_fact(
                ps,
                event_store,
                event_bus,
                entity_type=args.get("entity_type", ""),
                entity_id=args.get("entity_id"),
                properties=props,
                related_to=args.get("related_to"),
                relation_type=args.get("relation_type"),
            )

        registry.register(
            "assert_fact",
            _assert_fact,
            ToolDefinition(
                name="assert_fact",
                description=(
                    "Record a new fact or observation. Creates a note with "
                    "user-level provenance (highest confidence). Optionally "
                    "note a relationship to an existing entity."
                ),
                args=[
                    ToolArg(name="entity_type", description="Entity type name", required=True),
                    ToolArg(
                        name="properties",
                        description="Entity properties as JSON",
                        type="object",
                        required=True,
                    ),
                    ToolArg(name="entity_id", description="Optional entity ID"),
                    ToolArg(name="related_to", description="ID of entity to link to"),
                    ToolArg(name="relation_type", description="Link type for the relation"),
                ],
            ),
        )

    def _register_add_context(self, registry: ToolRegistry) -> None:
        ps = self._ps

        async def _add_context(args: dict[str, Any]) -> dict[str, str]:
            return await add_context(
                ps,
                entity_type=args.get("entity_type", ""),
                entity_id=args.get("entity_id", ""),
                context=args.get("context", ""),
            )

        registry.register(
            "add_context",
            _add_context,
            ToolDefinition(
                name="add_context",
                description=(
                    "Attach user context to an entity — e.g. 'we are in a dispute "
                    "with this tenant' or 'this property is being renovated'."
                ),
                args=[
                    ToolArg(name="entity_type", description="Entity type name", required=True),
                    ToolArg(name="entity_id", description="Entity ID to annotate", required=True),
                    ToolArg(name="context", description="Context text to attach", required=True),
                ],
            ),
        )
