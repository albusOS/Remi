"""AppFolio Delinquency report ingestion."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import structlog

from remi.documents.appfolio_schema import parse_delinquency_rows
from remi.knowledge.ingestion.base import IngestionResult
from remi.knowledge.ingestion.helpers import parse_address
from remi.models.documents import Document
from remi.models.memory import KnowledgeStore, Relationship
from remi.models.properties import (
    Lease,
    OccupancyStatus,
    PropertyStore,
    Tenant,
    TenantStatus,
    Unit,
    UnitStatus,
)
from remi.shared.text import slugify

_log = structlog.get_logger(__name__)

_TENANT_STATUS_MAP: dict[str, TenantStatus] = {
    "current": TenantStatus.CURRENT,
    "notice": TenantStatus.NOTICE,
    "evict": TenantStatus.EVICT,
}


async def ingest_delinquency(
    doc: Document,
    namespace: str,
    result: IngestionResult,
    kb: KnowledgeStore,
    ps: PropertyStore,
    upsert_entity: Any,
    upsert_property_safe: Any,
    ensure_manager: Any,
    upload_portfolio_id: str | None = None,
) -> None:
    parsed_rows = parse_delinquency_rows(doc.rows)

    # Scoped replace: clear stale units/leases for affected properties
    # before re-inserting from the fresh delinquency report.
    affected_property_ids: set[str] = set()
    for row in parsed_rows:
        affected_property_ids.add(slugify(f"property:{row.property_name}"))

    for prop_id in affected_property_ids:
        deleted_units = await ps.delete_units_by_property(prop_id)
        deleted_leases = await ps.delete_leases_by_property(prop_id)
        if deleted_units or deleted_leases:
            _log.info(
                "scoped_replace_cleared",
                property_id=prop_id,
                units_removed=deleted_units,
                leases_removed=deleted_leases,
                source_doc=doc.id,
            )

    # Collect the first non-empty manager tag per property so we can set
    # manager_tag on the KB entity and resolve portfolio during ingestion.
    prop_tag: dict[str, str] = {}
    for row in parsed_rows:
        pid = slugify(f"property:{row.property_name}")
        if pid not in prop_tag and row.tags:
            tag = row.tags.strip().split(",")[0].strip()
            if tag and tag.lower() != "month-to-month":
                prop_tag[pid] = tag

    for row in parsed_rows:
        prop_id = slugify(f"property:{row.property_name}")
        unit_id = slugify(f"unit:{row.property_name}:{row.unit_number or 'main'}")
        tenant_id = slugify(f"tenant:{row.tenant_name}:{row.property_name}")

        prop_props: dict[str, Any] = {
            "address": row.property_address,
            "name": row.property_name,
            "source_doc": doc.id,
        }
        if prop_id in prop_tag:
            prop_props["manager_tag"] = prop_tag[prop_id]

        await upsert_entity(
            prop_id,
            "appfolio_property",
            namespace,
            prop_props,
            result,
        )
        await upsert_entity(
            unit_id,
            "appfolio_unit",
            namespace,
            {
                "property_name": row.property_name,
                "unit_number": row.unit_number,
                "source_doc": doc.id,
            },
            result,
        )

        tenant_props: dict[str, Any] = {
            "name": row.tenant_name,
            "tenant_status": row.tenant_status,
            "monthly_rent": row.monthly_rent,
            "amount_owed": row.amount_owed,
            "subsidy_delinquent": row.subsidy_delinquent,
            "balance_0_30": row.balance_0_30,
            "balance_30_plus": row.balance_30_plus,
            "source_doc": doc.id,
        }
        if row.tags:
            tenant_props["tags"] = row.tags
        if row.last_payment_date:
            tenant_props["last_payment_date"] = row.last_payment_date.isoformat()
        if row.delinquency_notes:
            tenant_props["delinquency_notes"] = row.delinquency_notes

        await upsert_entity(
            tenant_id, "appfolio_delinquent_tenant", namespace, tenant_props, result
        )

        for src, rel, tgt in [
            (unit_id, "belongs_to", prop_id),
            (tenant_id, "occupies", unit_id),
            (tenant_id, "owes_balance_at", prop_id),
        ]:
            await kb.put_relationship(
                Relationship(source_id=src, target_id=tgt, relation_type=rel, namespace=namespace)
            )
            result.relationships_created += 1

        portfolio_id: str | None = upload_portfolio_id
        if portfolio_id is None:
            manager_tag = prop_tag.get(prop_id)
            if manager_tag:
                portfolio_id = await ensure_manager(manager_tag)

        addr = parse_address(row.property_address)
        await upsert_property_safe(
            prop_id,
            row.property_name,
            addr,
            portfolio_id=portfolio_id,
            source_document_id=doc.id,
        )

        await ps.upsert_unit(
            Unit(
                id=unit_id,
                property_id=prop_id,
                unit_number=row.unit_number or "main",
                status=UnitStatus.OCCUPIED,
                occupancy_status=OccupancyStatus.OCCUPIED,
                current_rent=Decimal(str(row.monthly_rent)) if row.monthly_rent else Decimal("0"),
                source_document_id=doc.id,
            )
        )

        tenant_status = _TENANT_STATUS_MAP.get(
            row.tenant_status.strip().lower(), TenantStatus.CURRENT
        )
        tags: list[str] = [t.strip() for t in (row.tags or "").split(",") if t.strip()]
        last_payment: date | None = row.last_payment_date.date() if row.last_payment_date else None

        await ps.upsert_tenant(
            Tenant(
                id=tenant_id,
                name=row.tenant_name,
                status=tenant_status,
                balance_owed=Decimal(str(row.amount_owed)),
                balance_0_30=Decimal(str(row.balance_0_30)),
                balance_30_plus=Decimal(str(row.balance_30_plus)),
                last_payment_date=last_payment,
                tags=tags,
                source_document_id=doc.id,
            )
        )

        lease_id = slugify(
            f"lease:{row.tenant_name}:{row.property_name}:{row.unit_number or 'main'}"
        )
        await ps.upsert_lease(
            Lease(
                id=lease_id,
                unit_id=unit_id,
                tenant_id=tenant_id,
                property_id=prop_id,
                start_date=date(2000, 1, 1),
                end_date=date(2099, 12, 31),
                monthly_rent=Decimal(str(row.monthly_rent)) if row.monthly_rent else Decimal("0"),
                source_document_id=doc.id,
            )
        )
