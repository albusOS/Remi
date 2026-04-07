"""Knowledge assertion endpoints — assert, correct, contextualize.

REST surface for user writes to domain knowledge. Same operations
available as agent tools in ``application/tools/assertions.py``.

All mutation endpoints produce ``ChangeSet`` events through the
``EventStore`` so corrections flow through the same event pipeline
as adapter imports.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from remi.application.tools.assertions import _add_context, _assert_fact
from remi.shell.api.dependencies import Ctr

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


class AssertFactRequest(BaseModel):
    entity_type: str
    entity_id: str | None = None
    properties: dict[str, str]
    related_to: str | None = None
    relation_type: str | None = None


class AddContextRequest(BaseModel):
    entity_type: str
    entity_id: str
    context: str


@router.post("/assert")
async def assert_fact(
    body: AssertFactRequest,
    c: Ctr,
) -> dict[str, str]:
    """Assert a new fact into the knowledge base with user provenance."""
    return await _assert_fact(
        c.property_store,
        c.event_store,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        properties=body.properties,
        related_to=body.related_to,
        relation_type=body.relation_type,
    )


@router.post("/context")
async def add_context(
    body: AddContextRequest,
    c: Ctr,
) -> dict[str, str]:
    """Attach user context/annotation to an entity."""
    return await _add_context(
        c.property_store,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        context=body.context,
    )
