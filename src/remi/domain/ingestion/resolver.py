"""Schema-driven ingestion resolver — LLM rows directly to domain models.

Maps LLM-extracted rows to domain models and persists them to PropertyStore
and KnowledgeStore in one pass. No intermediate event layer.

The resolver reads entity type names from the ontology and dispatches to
per-type persist functions that handle:
  - ID generation (composite slugs)
  - Property ensure (first-seen property + optional scope replace)
  - Manager tag classification (frequency analysis)
  - Type coercion (strings to enums, decimals, dates)
  - KB entity mirroring (every upsert also goes to the knowledge graph)

Report-level semantics:
  - rent_roll: each row is a Unit. Scope-replaces existing units per property.
  - delinquency: each row implies Unit + Tenant + Lease. Scope-replaces both.
  - lease_expiration: each row implies Unit + Tenant + Lease.
  - property_directory: each row is a Property with optional manager.
  - work_order: each row is a MaintenanceRequest.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import structlog

from remi.agent.graph.stores import KnowledgeStore
from remi.agent.graph.types import Entity, Relationship
from remi.domain.ingestion.base import IngestionResult, RowWarning
from remi.domain.ingestion.managers import ManagerResolver, classify_manager_values
from remi.domain.portfolio.models import (
    Address,
    Lease,
    LeaseStatus,
    MaintenanceCategory,
    MaintenanceRequest,
    MaintenanceStatus,
    OccupancyStatus,
    Priority,
    Property,
    Tenant,
    TenantStatus,
    Unit,
    UnitStatus,
)
from remi.domain.portfolio.protocols import PropertyStore
from remi.types.text import slugify

_log = structlog.get_logger(__name__)

_LEASE_START_FALLBACK = date(2000, 1, 1)
_LEASE_END_FALLBACK = date(2099, 12, 31)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def resolve_and_persist(
    rows: list[dict[str, Any]],
    *,
    report_type: str,
    platform: str,
    doc_id: str,
    namespace: str,
    kb: KnowledgeStore,
    ps: PropertyStore,
    manager_resolver: ManagerResolver,
    result: IngestionResult,
    upload_portfolio_id: str | None = None,
) -> None:
    """Map LLM-extracted rows to domain models and persist in one pass."""
    if not rows:
        return

    ctx = _BatchContext(
        platform=platform,
        report_type=report_type,
        doc_id=doc_id,
        namespace=namespace,
        kb=kb,
        ps=ps,
        manager_resolver=manager_resolver,
        result=result,
        upload_portfolio_id=upload_portfolio_id,
    )

    # Pass 1: collect manager tags for frequency classification
    for row in rows:
        row_type = _resolve_type(row.get("type", "raw_row"))
        if row_type in ("Unit", "Tenant", "Lease", "Property"):
            _collect_manager_tag(row, ctx)

    ctx.real_manager_tags = classify_manager_values(ctx.prop_manager_tags)

    # Pass 2: resolve and persist each row
    for i, row in enumerate(rows):
        row_type = _resolve_type(row.get("type", "raw_row"))
        handler = _ROW_PERSISTERS.get(row_type)
        if handler is None:
            ctx.result.rows_skipped += 1
            continue
        try:
            await handler(row, ctx)
            ctx.result.rows_accepted += 1
        except Exception:
            _log.warning(
                "row_persist_failed",
                row_type=row_type,
                doc_id=doc_id,
                exc_info=True,
            )
            ctx.result.persist_errors.append(RowWarning(
                row_index=i,
                row_type=row_type,
                field="*",
                issue="persist_failed",
                raw_value=str(row.get("property_address", ""))[:100],
            ))
            ctx.result.rows_rejected += 1

    _log.info(
        "resolve_complete",
        namespace=namespace,
        entities=result.entities_created,
        relationships=result.relationships_created,
        rows_accepted=result.rows_accepted,
        rows_rejected=result.rows_rejected,
        rows_skipped=result.rows_skipped,
        real_managers=len(ctx.real_manager_tags),
        tags_skipped=len(result.manager_tags_skipped),
    )


# ---------------------------------------------------------------------------
# Batch context — shared state across rows in a single document
# ---------------------------------------------------------------------------


class _BatchContext:
    __slots__ = (
        "platform", "report_type", "doc_id", "namespace",
        "kb", "ps", "manager_resolver", "result",
        "upload_portfolio_id", "seen_properties",
        "prop_manager_tags", "real_manager_tags", "property_portfolio",
    )

    def __init__(
        self,
        *,
        platform: str,
        report_type: str,
        doc_id: str,
        namespace: str,
        kb: KnowledgeStore,
        ps: PropertyStore,
        manager_resolver: ManagerResolver,
        result: IngestionResult,
        upload_portfolio_id: str | None,
    ) -> None:
        self.platform = platform
        self.report_type = report_type
        self.doc_id = doc_id
        self.namespace = namespace
        self.kb = kb
        self.ps = ps
        self.manager_resolver = manager_resolver
        self.result = result
        self.upload_portfolio_id = upload_portfolio_id
        self.seen_properties: set[str] = set()
        self.prop_manager_tags: dict[str, str] = {}
        self.real_manager_tags: set[str] = set()
        self.property_portfolio: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Type resolution — ontology names + legacy compat
# ---------------------------------------------------------------------------

_LEGACY_TYPE_MAP: dict[str, str] = {
    "unit": "Unit",
    "tenant_balance": "Tenant",
    "lease": "Lease",
    "property": "Property",
}


def _resolve_type(raw_type: str) -> str:
    return _LEGACY_TYPE_MAP.get(raw_type, raw_type)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


_OCCUPANCY_MAP: dict[str, OccupancyStatus] = {
    "occupied": OccupancyStatus.OCCUPIED,
    "notice_rented": OccupancyStatus.NOTICE_RENTED,
    "notice_unrented": OccupancyStatus.NOTICE_UNRENTED,
    "vacant_rented": OccupancyStatus.VACANT_RENTED,
    "vacant_unrented": OccupancyStatus.VACANT_UNRENTED,
}

_TENANT_STATUS_MAP: dict[str, TenantStatus] = {
    "current": TenantStatus.CURRENT,
    "notice": TenantStatus.NOTICE,
    "evict": TenantStatus.EVICT,
}

_UNIT_STATUS_FROM_OCCUPANCY: dict[OccupancyStatus, UnitStatus] = {
    OccupancyStatus.OCCUPIED: UnitStatus.OCCUPIED,
    OccupancyStatus.NOTICE_RENTED: UnitStatus.OCCUPIED,
    OccupancyStatus.NOTICE_UNRENTED: UnitStatus.OCCUPIED,
    OccupancyStatus.VACANT_RENTED: UnitStatus.VACANT,
    OccupancyStatus.VACANT_UNRENTED: UnitStatus.VACANT,
}

_MAINTENANCE_CATEGORY_MAP: dict[str, MaintenanceCategory] = {
    v.value: v for v in MaintenanceCategory
}
_MAINTENANCE_STATUS_MAP: dict[str, MaintenanceStatus] = {
    v.value: v for v in MaintenanceStatus
}
_PRIORITY_MAP: dict[str, Priority] = {v.value: v for v in Priority}


def _property_name(full_address: str) -> str:
    if " - " in full_address:
        return full_address.split(" - ")[0].strip()
    parts = full_address.split(",")
    return parts[0].strip() if len(parts) >= 2 else full_address.strip()


def _parse_address(raw: str) -> Address:
    name = _property_name(raw)
    parts = raw.rsplit(",", 1)
    city, state, zip_code = "Unknown", "XX", ""
    if len(parts) >= 2:
        tail = parts[1].strip().split()
        if len(tail) >= 2:
            state, zip_code = tail[0], tail[1]
        elif tail:
            state = tail[0]
    return Address(street=name, city=city, state=state, zip_code=zip_code)


def _to_decimal(val: Any, default: str = "0") -> Decimal:
    if val is None:
        return Decimal(default)
    try:
        return Decimal(str(val))
    except Exception:
        _log.warning("decimal_parse_fallback", raw_value=str(val)[:50], default=default)
        return Decimal(default)


def _to_date(val: Any) -> date | None:
    if val is None:
        return None
    if isinstance(val, date):
        return val
    from datetime import datetime as _dt

    s = str(val).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return _dt.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _to_int(val: Any) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _collect_manager_tag(row: dict[str, Any], ctx: _BatchContext) -> None:
    """Pre-scan: collect the first manager tag per property for classification."""
    raw_addr = str(row.get("property_address", "")).strip()
    name = _property_name(raw_addr) or raw_addr
    prop_id = slugify(f"property:{name}")

    tags_raw = str(row.get("tags") or "").strip()
    manager_raw = str(
        row.get("manager_name") or row.get("manager") or row.get("site_manager_name") or ""
    ).strip()

    tag = None
    if tags_raw:
        parts = [t.strip() for t in tags_raw.split(",") if t.strip()]
        tag = next((t for t in parts if t.lower() != "month-to-month"), None)
    if not tag and manager_raw:
        tag = manager_raw

    if tag and prop_id not in ctx.prop_manager_tags:
        ctx.prop_manager_tags[prop_id] = tag


# ---------------------------------------------------------------------------
# Property ensure — shared by all entity persisters
# ---------------------------------------------------------------------------


async def _ensure_property(
    row: dict[str, Any],
    ctx: _BatchContext,
    *,
    replace_units: bool = False,
    replace_leases: bool = False,
) -> str:
    """Ensure the property exists. Returns property_id."""
    raw_addr = str(row.get("property_address", "")).strip()
    name = _property_name(raw_addr) or raw_addr
    prop_id = slugify(f"property:{name}")

    if prop_id in ctx.seen_properties:
        return prop_id
    ctx.seen_properties.add(prop_id)

    # Scope replace for full-replace report types
    if replace_units:
        deleted = await ctx.ps.delete_units_by_property(prop_id)
        if deleted:
            _log.info("scoped_replace_units", property_id=prop_id, deleted=deleted)
    if replace_leases:
        deleted = await ctx.ps.delete_leases_by_property(prop_id)
        if deleted:
            _log.info("scoped_replace_leases", property_id=prop_id, deleted=deleted)

    # Resolve portfolio
    if ctx.upload_portfolio_id is not None:
        effective_pid = ctx.upload_portfolio_id
    elif prop_id in ctx.property_portfolio:
        effective_pid = ctx.property_portfolio[prop_id]
    else:
        existing = await ctx.ps.get_property(prop_id)
        effective_pid = (existing.portfolio_id if existing else None) or ""

    address = _parse_address(raw_addr)
    await ctx.ps.upsert_property(
        Property(
            id=prop_id,
            portfolio_id=effective_pid,
            name=name,
            address=address,
            source_document_id=ctx.doc_id,
        )
    )
    await _merge_kb(ctx, prop_id, f"{ctx.platform}_property", {
        "name": name,
        "address": address.one_line(),
        "source_doc": ctx.doc_id,
    })
    ctx.result.entities_created += 1

    # Resolve manager tag if present
    tag = ctx.prop_manager_tags.get(prop_id)
    if tag and tag in ctx.real_manager_tags:
        portfolio_id = await ctx.manager_resolver.ensure_manager(tag)
        ctx.property_portfolio[prop_id] = portfolio_id
    elif tag:
        ctx.result.manager_tags_skipped.append(tag)

    return prop_id


# ---------------------------------------------------------------------------
# Per-entity-type persisters
# ---------------------------------------------------------------------------

_RowPersister = Callable[["dict[str, Any]", _BatchContext], Any]


async def _persist_unit(row: dict[str, Any], ctx: _BatchContext) -> None:
    prop_id = await _ensure_property(row, ctx, replace_units=True)
    unit_num = str(row.get("unit_number") or "main").strip()
    unit_id = slugify(f"unit:{prop_id}:{unit_num}")

    occ_str = str(row.get("occupancy_status", "")).lower().replace("-", "_")
    occupancy = _OCCUPANCY_MAP.get(occ_str)
    unit_status = (
        _UNIT_STATUS_FROM_OCCUPANCY.get(occupancy, UnitStatus.VACANT)
        if occupancy else UnitStatus.VACANT
    )

    unit = Unit(
        id=unit_id,
        property_id=prop_id,
        unit_number=unit_num,
        status=unit_status,
        occupancy_status=occupancy,
        bedrooms=_to_int(row.get("bedrooms")),
        bathrooms=float(row["bathrooms"]) if row.get("bathrooms") is not None else None,
        sqft=_to_int(row.get("sqft")),
        market_rent=_to_decimal(row.get("market_rent")),
        current_rent=_to_decimal(row.get("monthly_rent") or row.get("current_rent")),
        days_vacant=_to_int(row.get("days_vacant")),
        listed_on_website=bool(row.get("posted_website", False)),
        listed_on_internet=bool(row.get("posted_internet", False)),
        source_document_id=ctx.doc_id,
    )
    await ctx.ps.upsert_unit(unit)

    kb_props: dict[str, str | int | float | bool | None] = {
        "property_id": prop_id, "unit_number": unit_num,
        "status": unit_status, "source_doc": ctx.doc_id,
    }
    if occupancy is not None:
        kb_props["occupancy_status"] = occupancy
    if unit.bedrooms is not None:
        kb_props["bedrooms"] = unit.bedrooms
    if unit.bathrooms is not None:
        kb_props["bathrooms"] = unit.bathrooms
    if unit.sqft is not None:
        kb_props["sqft"] = unit.sqft
    if unit.days_vacant is not None:
        kb_props["days_vacant"] = unit.days_vacant
    kb_props["listed_on_website"] = unit.listed_on_website
    kb_props["listed_on_internet"] = unit.listed_on_internet

    await _merge_kb(ctx, unit_id, f"{ctx.platform}_unit", kb_props)
    await ctx.kb.put_relationship(Relationship(
        source_id=unit_id, target_id=prop_id,
        relation_type="belongs_to", namespace=ctx.namespace,
    ))
    ctx.result.entities_created += 1
    ctx.result.relationships_created += 1


async def _persist_tenant(row: dict[str, Any], ctx: _BatchContext) -> None:
    """Delinquency rows: each row implies Unit + Tenant + Lease."""
    prop_id = await _ensure_property(row, ctx, replace_units=True, replace_leases=True)
    unit_num = str(row.get("unit_number") or "main").strip()
    unit_id = slugify(f"unit:{prop_id}:{unit_num}")
    tenant_name = str(row.get("tenant_name") or row.get("name") or "").strip()
    tenant_id = slugify(f"tenant:{tenant_name}:{prop_id}")
    lease_id = slugify(f"lease:{tenant_name}:{prop_id}:{unit_num}")

    # Implied Unit
    await ctx.ps.upsert_unit(Unit(
        id=unit_id, property_id=prop_id, unit_number=unit_num,
        status=UnitStatus.OCCUPIED, occupancy_status=OccupancyStatus.OCCUPIED,
        current_rent=_to_decimal(row.get("monthly_rent")),
        source_document_id=ctx.doc_id,
    ))
    await _merge_kb(ctx, unit_id, f"{ctx.platform}_unit", {
        "property_id": prop_id, "unit_number": unit_num,
        "status": UnitStatus.OCCUPIED, "source_doc": ctx.doc_id,
    })
    await ctx.kb.put_relationship(Relationship(
        source_id=unit_id, target_id=prop_id,
        relation_type="belongs_to", namespace=ctx.namespace,
    ))
    ctx.result.entities_created += 1
    ctx.result.relationships_created += 1

    # Tenant
    raw_status = row.get("tenant_status") or row.get("status") or "current"
    tenant_status_str = str(raw_status).strip().lower()
    tenant = Tenant(
        id=tenant_id, name=tenant_name,
        status=_TENANT_STATUS_MAP.get(tenant_status_str, TenantStatus.CURRENT),
        balance_owed=_to_decimal(row.get("amount_owed") or row.get("balance_owed")),
        balance_0_30=_to_decimal(row.get("balance_0_30")),
        balance_30_plus=_to_decimal(row.get("balance_30_plus")),
        last_payment_date=_to_date(row.get("last_payment_date")),
        tags=[t.strip() for t in str(row.get("tags") or "").split(",") if t.strip()],
        source_document_id=ctx.doc_id,
    )
    await ctx.ps.upsert_tenant(tenant)

    kb_entity_type = (
        f"{ctx.platform}_delinquent_tenant"
        if ctx.report_type == "delinquency"
        else f"{ctx.platform}_tenant"
    )
    tenant_props: dict[str, str | float | bool | None] = {
        "name": tenant_name, "status": tenant.status,
        "balance_owed": str(tenant.balance_owed),
        "balance_0_30": str(tenant.balance_0_30),
        "balance_30_plus": str(tenant.balance_30_plus),
        "source_doc": ctx.doc_id,
    }
    if tenant.last_payment_date:
        tenant_props["last_payment_date"] = tenant.last_payment_date.isoformat()
    if tenant.tags:
        tenant_props["tags"] = ",".join(tenant.tags)
    if tenant.phone:
        tenant_props["phone"] = tenant.phone
    await _merge_kb(ctx, tenant_id, kb_entity_type, tenant_props)
    ctx.result.entities_created += 1

    # Implied Lease
    await ctx.ps.upsert_lease(Lease(
        id=lease_id, unit_id=unit_id, tenant_id=tenant_id, property_id=prop_id,
        start_date=_LEASE_START_FALLBACK, end_date=_LEASE_END_FALLBACK,
        monthly_rent=_to_decimal(row.get("monthly_rent")),
        status=LeaseStatus.ACTIVE, source_document_id=ctx.doc_id,
    ))
    await _merge_kb(ctx, lease_id, f"{ctx.platform}_lease", {
        "unit_id": unit_id, "tenant_id": tenant_id, "property_id": prop_id,
        "monthly_rent": str(_to_decimal(row.get("monthly_rent"))),
        "status": LeaseStatus.ACTIVE, "source_doc": ctx.doc_id,
    })
    await ctx.kb.put_relationship(Relationship(
        source_id=tenant_id, target_id=unit_id,
        relation_type="leases", namespace=ctx.namespace,
    ))
    await ctx.kb.put_relationship(Relationship(
        source_id=tenant_id, target_id=prop_id,
        relation_type="owes_balance_at", namespace=ctx.namespace,
    ))
    ctx.result.entities_created += 1
    ctx.result.relationships_created += 2


async def _persist_lease(row: dict[str, Any], ctx: _BatchContext) -> None:
    prop_id = await _ensure_property(row, ctx)
    unit_num = str(row.get("unit_number") or "main").strip()
    unit_id = slugify(f"unit:{prop_id}:{unit_num}")
    tenant_name = str(row.get("tenant_name") or row.get("name") or "").strip()
    tenant_id = slugify(f"tenant:{tenant_name}:{prop_id}")
    lease_id = slugify(f"lease:{tenant_name}:{prop_id}:{unit_num}")

    monthly_rent = _to_decimal(row.get("monthly_rent"))
    has_active_lease = monthly_rent > 0 and bool(tenant_name)

    # Implied Unit
    await ctx.ps.upsert_unit(Unit(
        id=unit_id, property_id=prop_id, unit_number=unit_num,
        status=UnitStatus.OCCUPIED if has_active_lease else UnitStatus.VACANT,
        occupancy_status=OccupancyStatus.OCCUPIED if has_active_lease else None,
        sqft=_to_int(row.get("sqft")),
        market_rent=_to_decimal(row.get("market_rent")),
        current_rent=monthly_rent, source_document_id=ctx.doc_id,
    ))
    await _merge_kb(ctx, unit_id, f"{ctx.platform}_unit", {
        "property_id": prop_id, "unit_number": unit_num,
        "status": UnitStatus.OCCUPIED if has_active_lease else UnitStatus.VACANT,
        "source_doc": ctx.doc_id,
    })
    await ctx.kb.put_relationship(Relationship(
        source_id=unit_id, target_id=prop_id,
        relation_type="belongs_to", namespace=ctx.namespace,
    ))
    ctx.result.entities_created += 1
    ctx.result.relationships_created += 1

    # Implied Tenant
    await ctx.ps.upsert_tenant(Tenant(
        id=tenant_id, name=tenant_name, status=TenantStatus.CURRENT,
        phone=str(row.get("phone_numbers") or row.get("phone") or "").strip() or None,
        source_document_id=ctx.doc_id,
    ))
    await _merge_kb(ctx, tenant_id, f"{ctx.platform}_tenant", {
        "name": tenant_name, "status": TenantStatus.CURRENT, "source_doc": ctx.doc_id,
    })
    ctx.result.entities_created += 1

    # Lease
    start = _to_date(row.get("move_in_date") or row.get("start_date"))
    end = _to_date(row.get("lease_expires") or row.get("end_date"))
    lease = Lease(
        id=lease_id, unit_id=unit_id, tenant_id=tenant_id, property_id=prop_id,
        start_date=start or _LEASE_START_FALLBACK,
        end_date=end or _LEASE_END_FALLBACK,
        monthly_rent=monthly_rent,
        market_rent=_to_decimal(row.get("market_rent")),
        deposit=_to_decimal(row.get("deposit")),
        is_month_to_month=bool(row.get("is_month_to_month", False)),
        status=LeaseStatus.ACTIVE, source_document_id=ctx.doc_id,
    )
    await ctx.ps.upsert_lease(lease)

    lease_props: dict[str, str | int | float | bool | None] = {
        "unit_id": unit_id, "tenant_id": tenant_id, "property_id": prop_id,
        "monthly_rent": str(monthly_rent),
        "is_month_to_month": str(lease.is_month_to_month),
        "status": LeaseStatus.ACTIVE, "source_doc": ctx.doc_id,
    }
    if start:
        lease_props["start_date"] = start.isoformat()
    if end:
        lease_props["end_date"] = end.isoformat()
    await _merge_kb(ctx, lease_id, f"{ctx.platform}_lease", lease_props)
    await ctx.kb.put_relationship(Relationship(
        source_id=tenant_id, target_id=unit_id,
        relation_type="leases", namespace=ctx.namespace,
    ))
    await ctx.kb.put_relationship(Relationship(
        source_id=tenant_id, target_id=prop_id,
        relation_type="owes_balance_at", namespace=ctx.namespace,
    ))
    ctx.result.entities_created += 1
    ctx.result.relationships_created += 2


async def _persist_property(row: dict[str, Any], ctx: _BatchContext) -> None:
    await _ensure_property(row, ctx)


async def _persist_maintenance(row: dict[str, Any], ctx: _BatchContext) -> None:
    prop_id = await _ensure_property(row, ctx)
    unit_num = str(row.get("unit_number") or row.get("unit_id") or "main").strip()
    unit_id = slugify(f"unit:{prop_id}:{unit_num}")
    title = str(row.get("title") or "").strip()
    request_id = slugify(f"maint:{prop_id}:{unit_num}:{title or 'request'}")

    cat_str = str(row.get("category") or "general").strip().lower()
    status_str = str(row.get("status") or "open").strip().lower()
    priority_str = str(row.get("priority") or "medium").strip().lower()

    tenant_name = str(row.get("tenant_name") or row.get("tenant_id") or "").strip()
    tenant_id = slugify(f"tenant:{tenant_name}:{prop_id}") if tenant_name else None

    mr = MaintenanceRequest(
        id=request_id, unit_id=unit_id, property_id=prop_id,
        tenant_id=tenant_id,
        category=_MAINTENANCE_CATEGORY_MAP.get(cat_str, MaintenanceCategory.GENERAL),
        priority=_PRIORITY_MAP.get(priority_str, Priority.MEDIUM),
        title=title,
        description=str(row.get("description") or "").strip(),
        status=_MAINTENANCE_STATUS_MAP.get(status_str, MaintenanceStatus.OPEN),
        cost=_to_decimal(row.get("cost")),
        vendor=str(row.get("vendor") or "").strip() or None,
    )
    await ctx.ps.upsert_maintenance_request(mr)

    maint_props: dict[str, str | int | float | bool | None] = {
        "unit_id": unit_id, "property_id": prop_id,
        "category": mr.category, "priority": mr.priority,
        "status": mr.status, "source_doc": ctx.doc_id,
    }
    if title:
        maint_props["title"] = title
    if tenant_id:
        maint_props["tenant_id"] = tenant_id
    if mr.vendor:
        maint_props["vendor"] = mr.vendor
    if mr.cost:
        maint_props["cost"] = str(mr.cost)

    await _merge_kb(ctx, request_id, f"{ctx.platform}_maintenance_request", maint_props)
    await ctx.kb.put_relationship(Relationship(
        source_id=request_id, target_id=unit_id,
        relation_type="affects", namespace=ctx.namespace,
    ))
    ctx.result.entities_created += 1
    ctx.result.relationships_created += 1


# ---------------------------------------------------------------------------
# Persister registry
# ---------------------------------------------------------------------------

_ROW_PERSISTERS: dict[str, _RowPersister] = {
    "Unit": _persist_unit,
    "Tenant": _persist_tenant,
    "Lease": _persist_lease,
    "Property": _persist_property,
    "MaintenanceRequest": _persist_maintenance,
}


# ---------------------------------------------------------------------------
# KB merge helper
# ---------------------------------------------------------------------------


async def _merge_kb(
    ctx: _BatchContext,
    entity_id: str,
    entity_type: str,
    new_props: dict[str, str | int | float | bool | None],
) -> None:
    existing = await ctx.kb.get_entity(ctx.namespace, entity_id)
    if existing:
        merged = {**existing.properties, **new_props}
        await ctx.kb.put_entity(Entity(
            entity_id=entity_id, entity_type=existing.entity_type,
            namespace=ctx.namespace, properties=merged,
        ))
    else:
        await ctx.kb.put_entity(Entity(
            entity_id=entity_id, entity_type=entity_type,
            namespace=ctx.namespace, properties=dict(new_props),
        ))
