"""Canonical ingestion engine — applies IngestionEvents to stores.

Consumes a list of ``IngestionEvent`` objects emitted by a source adapter and
writes them to ``KnowledgeStore`` (KB graph) and ``PropertyStore`` (domain
models).  This module knows nothing about AppFolio or any other source
platform; it only speaks the canonical event vocabulary.

Two-pass processing:
  Pass 1 — collect ManagerObserved events, run frequency classification once
            across the full batch to determine which tags are real managers.
  Pass 2 — apply events in order: ScopeReplace → PropertyObserved →
            ManagerObserved → UnitObserved → TenantObserved → LeaseObserved.

KB entity type strings reflect the source platform via ``event.source.platform``
and ``event.source.report_type``, keeping the graph queryable by origin while
keeping this file source-agnostic.
"""

from __future__ import annotations

from datetime import date

import structlog

from remi.ingestion.events import (
    IngestionEvent,
    LeaseObserved,
    ManagerObserved,
    PropertyObserved,
    ScopeReplace,
    TenantObserved,
    UnitObserved,
)
from remi.graph.stores import KnowledgeStore
from remi.graph.types import Entity, Relationship
from remi.ingestion.base import IngestionResult
from remi.ingestion.managers import ManagerResolver, classify_manager_values
from remi.portfolio.models import (
    Lease,
    Property,
    Tenant,
    Unit,
)
from remi.portfolio.protocols import PropertyStore

logger = structlog.get_logger(__name__)

# Sentinel dates used only as a last resort when a Lease domain model must be
# created but the source report did not carry real dates.  These are isolated
# here rather than scattered through the adapter or caller logic.
_LEASE_START_FALLBACK = date(2000, 1, 1)
_LEASE_END_FALLBACK = date(2099, 12, 31)


async def apply_events(
    events: list[IngestionEvent],
    namespace: str,
    kb: KnowledgeStore,
    ps: PropertyStore,
    manager_resolver: ManagerResolver,
    result: IngestionResult,
    upload_portfolio_id: str | None = None,
) -> None:
    """Apply a list of canonical events to the knowledge and property stores.

    ``upload_portfolio_id``: when provided, overrides any manager-derived
    portfolio for every property seen in this batch.
    """
    if not events:
        return

    # ------------------------------------------------------------------
    # Pass 1 — collect manager observations for frequency classification
    # ------------------------------------------------------------------
    # Map each property_id to the first manager tag seen for it (same logic
    # as the old ingest_report: first non-empty tag per property wins).
    prop_manager_tag: dict[str, str] = {}
    for event in events:
        if isinstance(event, ManagerObserved) and event.property_id not in prop_manager_tag:
            prop_manager_tag[event.property_id] = event.manager_tag

    real_manager_tags: set[str] = classify_manager_values(prop_manager_tag)

    # property_id → resolved portfolio_id (populated during ManagerObserved handling)
    property_portfolio: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Pass 2 — apply events in order
    # ------------------------------------------------------------------
    for event in events:
        match event:
            case ScopeReplace():
                await _apply_scope_replace(event, ps)

            case PropertyObserved():
                await _apply_property(
                    event, ps, kb, namespace, result,
                    upload_portfolio_id, property_portfolio,
                )

            case ManagerObserved():
                await _apply_manager(
                    event, manager_resolver, real_manager_tags,
                    result, property_portfolio,
                )

            case UnitObserved():
                await _apply_unit(event, ps, kb, namespace, result)

            case TenantObserved():
                await _apply_tenant(event, ps, kb, namespace, result)

            case LeaseObserved():
                await _apply_lease(event, ps, kb, namespace, result)

    logger.info(
        "engine_apply_complete",
        namespace=namespace,
        entities_created=result.entities_created,
        relationships_created=result.relationships_created,
        real_managers=len(real_manager_tags),
        tags_skipped=len(result.manager_tags_skipped),
    )


# ---------------------------------------------------------------------------
# Per-event handlers
# ---------------------------------------------------------------------------


async def _apply_scope_replace(event: ScopeReplace, ps: PropertyStore) -> None:
    if event.replace_units:
        deleted = await ps.delete_units_by_property(event.property_id)
        if deleted:
            logger.info(
                "scoped_replace_units",
                property_id=event.property_id,
                deleted=deleted,
            )
    if event.replace_leases:
        deleted = await ps.delete_leases_by_property(event.property_id)
        if deleted:
            logger.info(
                "scoped_replace_leases",
                property_id=event.property_id,
                deleted=deleted,
            )


async def _apply_property(
    event: PropertyObserved,
    ps: PropertyStore,
    kb: KnowledgeStore,
    namespace: str,
    result: IngestionResult,
    upload_portfolio_id: str | None,
    property_portfolio: dict[str, str],
) -> None:
    # Resolve portfolio_id: upload override > manager-derived > existing > empty
    if upload_portfolio_id is not None:
        effective_pid = upload_portfolio_id
    elif event.property_id in property_portfolio:
        effective_pid = property_portfolio[event.property_id]
    else:
        existing = await ps.get_property(event.property_id)
        effective_pid = (existing.portfolio_id if existing else None) or ""

    await ps.upsert_property(
        Property(
            id=event.property_id,
            portfolio_id=effective_pid,
            name=event.name,
            address=event.address,
            source_document_id=event.source.doc_id,
        )
    )

    await _merge_kb_entity(
        kb,
        namespace=namespace,
        entity_id=event.property_id,
        entity_type=f"{event.source.platform}_property",
        new_props={
            "name": event.name,
            "address": event.address.one_line(),
            "source_doc": event.source.doc_id,
        },
    )
    result.entities_created += 1


async def _apply_manager(
    event: ManagerObserved,
    manager_resolver: ManagerResolver,
    real_manager_tags: set[str],
    result: IngestionResult,
    property_portfolio: dict[str, str],
) -> None:
    tag = prop_manager_tag_for(event)
    if tag in real_manager_tags:
        portfolio_id = await manager_resolver.ensure_manager(tag)
        property_portfolio[event.property_id] = portfolio_id
    else:
        result.manager_tags_skipped.append(tag)


def prop_manager_tag_for(event: ManagerObserved) -> str:
    return event.manager_tag


async def _apply_unit(
    event: UnitObserved,
    ps: PropertyStore,
    kb: KnowledgeStore,
    namespace: str,
    result: IngestionResult,
) -> None:
    await ps.upsert_unit(
        Unit(
            id=event.unit_id,
            property_id=event.property_id,
            unit_number=event.unit_number,
            bedrooms=event.bedrooms,
            bathrooms=event.bathrooms,
            sqft=event.sqft,
            market_rent=event.market_rent,
            current_rent=event.current_rent,
            status=event.status,
            occupancy_status=event.occupancy_status,
            days_vacant=event.days_vacant,
            listed_on_website=event.listed_on_website,
            listed_on_internet=event.listed_on_internet,
            source_document_id=event.source.doc_id,
        )
    )

    unit_props: dict[str, str | int | float | bool | None] = {
        "property_id": event.property_id,
        "unit_number": event.unit_number,
        "status": event.status,
        "source_doc": event.source.doc_id,
    }
    if event.occupancy_status is not None:
        unit_props["occupancy_status"] = event.occupancy_status
    if event.bedrooms is not None:
        unit_props["bedrooms"] = event.bedrooms
    if event.bathrooms is not None:
        unit_props["bathrooms"] = event.bathrooms
    if event.sqft is not None:
        unit_props["sqft"] = event.sqft
    if event.days_vacant is not None:
        unit_props["days_vacant"] = event.days_vacant
    unit_props["listed_on_website"] = event.listed_on_website
    unit_props["listed_on_internet"] = event.listed_on_internet

    await _merge_kb_entity(
        kb,
        namespace=namespace,
        entity_id=event.unit_id,
        entity_type=f"{event.source.platform}_unit",
        new_props=unit_props,
    )
    await kb.put_relationship(
        Relationship(
            source_id=event.unit_id,
            target_id=event.property_id,
            relation_type="belongs_to",
            namespace=namespace,
        )
    )
    result.entities_created += 1
    result.relationships_created += 1


async def _apply_tenant(
    event: TenantObserved,
    ps: PropertyStore,
    kb: KnowledgeStore,
    namespace: str,
    result: IngestionResult,
) -> None:
    await ps.upsert_tenant(
        Tenant(
            id=event.tenant_id,
            name=event.name,
            phone=event.phone,
            status=event.status,
            balance_owed=event.balance_owed,
            balance_0_30=event.balance_0_30,
            balance_30_plus=event.balance_30_plus,
            last_payment_date=event.last_payment_date,
            tags=event.tags,
            source_document_id=event.source.doc_id,
        )
    )

    tenant_props: dict[str, str | float | bool | None] = {
        "name": event.name,
        "status": event.status,
        "balance_owed": str(event.balance_owed),
        "balance_0_30": str(event.balance_0_30),
        "balance_30_plus": str(event.balance_30_plus),
        "source_doc": event.source.doc_id,
    }
    if event.last_payment_date:
        tenant_props["last_payment_date"] = event.last_payment_date.isoformat()
    if event.tags:
        tenant_props["tags"] = ",".join(event.tags)
    if event.phone:
        tenant_props["phone"] = event.phone

    # Determine KB entity type from report context
    report_type = event.source.report_type
    entity_type = (
        f"{event.source.platform}_delinquent_tenant"
        if report_type == "delinquency"
        else f"{event.source.platform}_tenant"
    )

    await _merge_kb_entity(
        kb,
        namespace=namespace,
        entity_id=event.tenant_id,
        entity_type=entity_type,
        new_props=tenant_props,
    )
    result.entities_created += 1


async def _apply_lease(
    event: LeaseObserved,
    ps: PropertyStore,
    kb: KnowledgeStore,
    namespace: str,
    result: IngestionResult,
) -> None:
    # Use fallback dates only at the PropertyStore boundary.  None dates are
    # honest in the event; the domain model requires concrete dates.
    effective_start = event.start_date or _LEASE_START_FALLBACK
    effective_end = event.end_date or _LEASE_END_FALLBACK

    await ps.upsert_lease(
        Lease(
            id=event.lease_id,
            unit_id=event.unit_id,
            tenant_id=event.tenant_id,
            property_id=event.property_id,
            start_date=effective_start,
            end_date=effective_end,
            monthly_rent=event.monthly_rent,
            deposit=event.deposit,
            market_rent=event.market_rent,
            is_month_to_month=event.is_month_to_month,
            status=event.status,
            source_document_id=event.source.doc_id,
        )
    )

    lease_props: dict[str, str | int | float | bool | None] = {
        "unit_id": event.unit_id,
        "tenant_id": event.tenant_id,
        "property_id": event.property_id,
        "monthly_rent": str(event.monthly_rent),
        "is_month_to_month": str(event.is_month_to_month),
        "status": event.status,
        "source_doc": event.source.doc_id,
    }
    if event.start_date:
        lease_props["start_date"] = event.start_date.isoformat()
    if event.end_date:
        lease_props["end_date"] = event.end_date.isoformat()

    await _merge_kb_entity(
        kb,
        namespace=namespace,
        entity_id=event.lease_id,
        entity_type=f"{event.source.platform}_lease",
        new_props=lease_props,
    )
    await kb.put_relationship(
        Relationship(
            source_id=event.tenant_id,
            target_id=event.unit_id,
            relation_type="leases",
            namespace=namespace,
        )
    )
    await kb.put_relationship(
        Relationship(
            source_id=event.tenant_id,
            target_id=event.property_id,
            relation_type="owes_balance_at",
            namespace=namespace,
        )
    )
    result.entities_created += 1
    result.relationships_created += 2


# ---------------------------------------------------------------------------
# KB entity merge helper
# ---------------------------------------------------------------------------


async def _merge_kb_entity(
    kb: KnowledgeStore,
    *,
    namespace: str,
    entity_id: str,
    entity_type: str,
    new_props: dict[str, str | int | float | bool | None],
) -> None:
    """Merge new properties into an existing KB entity, or create it fresh."""
    existing = await kb.get_entity(namespace, entity_id)
    if existing:
        merged = {**existing.properties, **new_props}
        await kb.put_entity(
            Entity(
                entity_id=entity_id,
                entity_type=existing.entity_type,
                namespace=namespace,
                properties=merged,
            )
        )
    else:
        await kb.put_entity(
            Entity(
                entity_id=entity_id,
                entity_type=entity_type,
                namespace=namespace,
                properties=dict(new_props),
            )
        )
