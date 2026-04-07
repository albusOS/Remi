"""Shared ingestion context — PropertyStore writes + provenance tracking.

All entity writes go through PropertyStore only. The ProjectingPropertyStore
decorator auto-creates structural graph edges from FK fields. This module
adds EXTRACTED_FROM provenance edges linking entities back to their source
document via KnowledgeWriter.
"""

from __future__ import annotations

from typing import Any

import structlog

from remi.application.core.models import Property
from remi.application.core.models.enums import ReportType
from remi.application.core.protocols import KBRelationship, KnowledgeWriter, PropertyStore
from remi.application.services.ingestion.base import (
    IngestionResult,
    ReviewItem,
    ReviewKind,
    ReviewOption,
    ReviewSeverity,
)
from remi.application.services.ingestion.managers import ManagerResolver
from remi.application.services.ingestion.resolver import parse_address, property_name
from remi.types.identity import property_id as _property_id

_log = structlog.get_logger(__name__)


class IngestionCtx:
    """Shared mutable state across rows in a single document."""

    __slots__ = (
        "platform",
        "report_type",
        "doc_id",
        "namespace",
        "kb",
        "ps",
        "manager_resolver",
        "result",
        "upload_manager_id",
        "seen_properties",
        "prop_manager_tags",
        "real_manager_tags",
        "property_manager",
        "extracted_entity_ids",
    )

    def __init__(
        self,
        *,
        platform: str,
        report_type: ReportType,
        doc_id: str,
        namespace: str,
        kb: KnowledgeWriter,
        ps: PropertyStore,
        manager_resolver: ManagerResolver,
        result: IngestionResult,
        upload_manager_id: str | None = None,
    ) -> None:
        self.platform = platform
        self.report_type = report_type
        self.doc_id = doc_id
        self.namespace = namespace
        self.kb = kb
        self.ps = ps
        self.manager_resolver = manager_resolver
        self.result = result
        self.upload_manager_id = upload_manager_id
        self.seen_properties: set[str] = set()
        self.prop_manager_tags: dict[str, str] = {}
        self.real_manager_tags: set[str] = set()
        self.property_manager: dict[str, str] = {}
        self.extracted_entity_ids: list[tuple[str, str]] = []


async def record_extracted(
    ctx: IngestionCtx,
    entity_id: str,
    entity_type: str,
) -> None:
    """Record that this entity was extracted from the current document.

    Creates an EXTRACTED_FROM edge in the knowledge graph and tracks
    the entity for later Document FK wiring.
    """
    ctx.extracted_entity_ids.append((entity_id, entity_type))
    ctx.result.entities_created += 1

    await ctx.kb.put_relationship(
        KBRelationship(
            source_id=entity_id,
            target_id=ctx.doc_id,
            relation_type="EXTRACTED_FROM",
            namespace=ctx.namespace,
        )
    )
    ctx.result.relationships_created += 1


async def ensure_property(
    row: dict[str, Any],
    ctx: IngestionCtx,
) -> str:
    """Ensure the property exists. Returns property_id.

    Replace semantics are derived from ``ctx.report_type`` so that each report
    type owns only the data it is authoritative over:

    - ``rent_roll``         → replaces units (authoritative unit inventory)
    - ``delinquency``       → replaces leases only (authoritative balance state;
                              does *not* touch unit inventory)
    - ``lease_expiration``  → no replacement (merge-only; does not own inventory)
    - ``property_directory`` → no replacement (additive; establishes registry)
    """
    raw_addr = str(row.get("property_address", "")).strip()
    name = property_name(raw_addr) or raw_addr
    prop_id = _property_id(name)

    if prop_id in ctx.seen_properties:
        return prop_id
    ctx.seen_properties.add(prop_id)

    # Ingestion is now additive — units and leases accumulate across reports.
    # Reconciliation happens at the row level (persist_lease marks displaced
    # leases TERMINATED; persist_tenant inserts BalanceObservations).
    _ = ctx.report_type  # kept for future report-type-specific logic

    existing = await ctx.ps.get_property(prop_id)

    if ctx.upload_manager_id is not None:
        mid: str | None = ctx.upload_manager_id
    elif prop_id in ctx.property_manager:
        mid = ctx.property_manager[prop_id]
    else:
        mid = existing.manager_id if existing else None

    address = parse_address(raw_addr)
    tag = ctx.prop_manager_tags.get(prop_id)

    if tag and tag in ctx.real_manager_tags:
        resolution = await ctx.manager_resolver.ensure_manager(tag)
        ctx.property_manager[prop_id] = resolution.manager_id
        mid = resolution.manager_id

        if resolution.created_new:
            ctx.result.review_items.append(
                ReviewItem(
                    kind=ReviewKind.MANAGER_INFERRED,
                    severity=ReviewSeverity.INFO,
                    message=(f"Created new manager '{resolution.manager_name}' from tag '{tag}'"),
                    entity_type="PropertyManager",
                    entity_id=resolution.manager_id,
                )
            )
        elif resolution.alias_matched:
            ctx.result.review_items.append(
                ReviewItem(
                    kind=ReviewKind.ENTITY_MATCH,
                    severity=ReviewSeverity.WARNING,
                    message=(
                        f"Matched tag '{resolution.alias_from}' to existing "
                        f"manager '{resolution.alias_to}'"
                    ),
                    entity_type="PropertyManager",
                    entity_id=resolution.manager_id,
                    raw_value=resolution.alias_from,
                    suggestion=resolution.alias_to,
                    options=[
                        ReviewOption(
                            id=resolution.manager_id,
                            label=str(resolution.alias_to),
                        ),
                        ReviewOption(
                            id="new",
                            label=f"Create '{resolution.alias_from}' as new manager",
                        ),
                    ],
                )
            )
    elif tag:
        ctx.result.manager_tags_skipped.append(tag)

    await ctx.ps.upsert_property(
        Property(
            id=prop_id,
            manager_id=mid,
            name=name,
            address=address,
            source_document_id=ctx.doc_id,
        )
    )
    await record_extracted(ctx, prop_id, "Property")

    return prop_id
