"""Declarative report schemas and unified ingestion loop.

Each AppFolio report type is described by a ``ReportSchema`` that declares:
  - How to parse raw rows into typed dataclasses
  - Which domain entities the report produces
  - How manager tags are extracted
  - Whether stale data should be cleared before re-ingesting

The single ``ingest_report()`` function replaces the four bespoke handler
files. Adding a new report type means adding a schema definition — not a
new Python module.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import structlog

from remi.documents.appfolio_schema import (
    AppFolioReportType,
    DelinquencyRow,
    LeaseExpirationRow,
    RentRollRow,
    parse_delinquency_rows,
    parse_lease_expiration_rows,
    parse_property_name,
    parse_rent_roll_rows,
)
from remi.knowledge.ingestion.base import IngestionResult
from remi.knowledge.ingestion.helpers import occupancy_to_unit_status, parse_address
from remi.knowledge.ingestion.managers import (
    ManagerExtraction,
    ManagerResolver,
    classify_manager_values,
    extract_manager_tag,
)
from remi.models.memory import Entity, KnowledgeStore, Relationship
from remi.models.properties import (
    Lease,
    OccupancyStatus,
    Property,
    PropertyStore,
    Tenant,
    TenantStatus,
    Unit,
    UnitStatus,
)
from remi.shared.text import slugify

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Row adapter protocol — thin wrappers over the typed appfolio_schema rows
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


@dataclass(frozen=True)
class ReportSchema:
    """Declarative description of an AppFolio report type's ingestion behavior."""

    report_type: str
    parse_fn: Callable[[list[dict[str, Any]]], Sequence[Any]]
    manager_extraction: ManagerExtraction
    manager_field: str | None
    scoped_replace: bool
    produces_units: bool
    produces_tenants: bool
    produces_leases: bool
    extract_kb_entities: Callable[[Any, str, str], list[_KBEntity]]
    extract_kb_relationships: Callable[[Any, str], list[_KBRelationship]]
    extract_domain_models: Callable[[Any, str, str | None], _DomainModels]


@dataclass(frozen=True)
class _KBEntity:
    entity_id: str
    entity_type: str
    properties: dict[str, Any]


@dataclass(frozen=True)
class _KBRelationship:
    source_id: str
    target_id: str
    relation_type: str


@dataclass
class _DomainModels:
    """Domain models produced from a single row."""

    prop_id: str
    prop_name: str
    prop_address: str
    unit: Unit | None = None
    tenant: Tenant | None = None
    lease: Lease | None = None


# ---------------------------------------------------------------------------
# Per-schema extractors — pure functions, no I/O
# ---------------------------------------------------------------------------

# -- Rent Roll --

def _rent_roll_kb_entities(
    row: RentRollRow, namespace: str, doc_id: str,
) -> list[_KBEntity]:
    prop_id = slugify(f"property:{row.property_name}")
    unit_id = slugify(f"unit:{row.property_name}:{row.unit_number or 'main'}")

    prop_ent = _KBEntity(
        entity_id=prop_id,
        entity_type="appfolio_property",
        properties={
            "address": row.property_address,
            "name": row.property_name,
            "source_doc": doc_id,
        },
    )

    unit_props: dict[str, Any] = {
        "property_name": row.property_name,
        "unit_number": row.unit_number,
        "occupancy_status": row.occupancy_status,
        "source_doc": doc_id,
    }
    if row.bedrooms is not None:
        unit_props["bedrooms"] = row.bedrooms
    if row.bathrooms is not None:
        unit_props["bathrooms"] = row.bathrooms
    if row.lease_start is not None:
        unit_props["lease_start"] = row.lease_start.isoformat()
    if row.lease_end is not None:
        unit_props["lease_end"] = row.lease_end.isoformat()
    if row.days_vacant is not None:
        unit_props["days_vacant"] = row.days_vacant
    if row.notes:
        unit_props["notes"] = row.notes
    unit_props["posted_website"] = row.posted_website
    unit_props["posted_internet"] = row.posted_internet

    unit_ent = _KBEntity(entity_id=unit_id, entity_type="appfolio_unit", properties=unit_props)
    return [prop_ent, unit_ent]


def _rent_roll_kb_rels(row: RentRollRow, namespace: str) -> list[_KBRelationship]:
    prop_id = slugify(f"property:{row.property_name}")
    unit_id = slugify(f"unit:{row.property_name}:{row.unit_number or 'main'}")
    return [_KBRelationship(source_id=unit_id, target_id=prop_id, relation_type="belongs_to")]


def _rent_roll_domain(
    row: RentRollRow, doc_id: str, portfolio_id: str | None,
) -> _DomainModels:
    prop_id = slugify(f"property:{row.property_name}")
    unit_id = slugify(f"unit:{row.property_name}:{row.unit_number or 'main'}")
    occupancy = _OCCUPANCY_MAP.get(row.occupancy_status)
    unit_status = occupancy_to_unit_status(occupancy)

    return _DomainModels(
        prop_id=prop_id,
        prop_name=row.property_name,
        prop_address=row.property_address,
        unit=Unit(
            id=unit_id,
            property_id=prop_id,
            unit_number=row.unit_number or "main",
            bedrooms=row.bedrooms,
            bathrooms=row.bathrooms,
            status=unit_status,
            occupancy_status=occupancy,
            days_vacant=row.days_vacant,
            listed_on_website=row.posted_website,
            listed_on_internet=row.posted_internet,
            source_document_id=doc_id,
        ),
    )


# -- Delinquency --

def _delinquency_kb_entities(
    row: DelinquencyRow, namespace: str, doc_id: str,
) -> list[_KBEntity]:
    prop_id = slugify(f"property:{row.property_name}")
    unit_id = slugify(f"unit:{row.property_name}:{row.unit_number or 'main'}")
    tenant_id = slugify(f"tenant:{row.tenant_name}:{row.property_name}")

    prop_props: dict[str, Any] = {
        "address": row.property_address,
        "name": row.property_name,
        "source_doc": doc_id,
    }
    if row.tags:
        tag = row.tags.strip().split(",")[0].strip()
        if tag and tag.lower() != "month-to-month":
            prop_props["manager_tag"] = tag

    entities = [
        _KBEntity(entity_id=prop_id, entity_type="appfolio_property", properties=prop_props),
        _KBEntity(
            entity_id=unit_id,
            entity_type="appfolio_unit",
            properties={
                "property_name": row.property_name,
                "unit_number": row.unit_number,
                "source_doc": doc_id,
            },
        ),
    ]

    tenant_props: dict[str, Any] = {
        "name": row.tenant_name,
        "tenant_status": row.tenant_status,
        "monthly_rent": row.monthly_rent,
        "amount_owed": row.amount_owed,
        "subsidy_delinquent": row.subsidy_delinquent,
        "balance_0_30": row.balance_0_30,
        "balance_30_plus": row.balance_30_plus,
        "source_doc": doc_id,
    }
    if row.tags:
        tenant_props["tags"] = row.tags
    if row.last_payment_date:
        tenant_props["last_payment_date"] = row.last_payment_date.isoformat()
    if row.delinquency_notes:
        tenant_props["delinquency_notes"] = row.delinquency_notes

    entities.append(
        _KBEntity(
            entity_id=tenant_id,
            entity_type="appfolio_delinquent_tenant",
            properties=tenant_props,
        )
    )
    return entities


def _delinquency_kb_rels(row: DelinquencyRow, namespace: str) -> list[_KBRelationship]:
    prop_id = slugify(f"property:{row.property_name}")
    unit_id = slugify(f"unit:{row.property_name}:{row.unit_number or 'main'}")
    tenant_id = slugify(f"tenant:{row.tenant_name}:{row.property_name}")
    return [
        _KBRelationship(source_id=unit_id, target_id=prop_id, relation_type="belongs_to"),
        _KBRelationship(source_id=tenant_id, target_id=unit_id, relation_type="occupies"),
        _KBRelationship(source_id=tenant_id, target_id=prop_id, relation_type="owes_balance_at"),
    ]


def _delinquency_domain(
    row: DelinquencyRow, doc_id: str, portfolio_id: str | None,
) -> _DomainModels:
    prop_id = slugify(f"property:{row.property_name}")
    unit_id = slugify(f"unit:{row.property_name}:{row.unit_number or 'main'}")
    tenant_id = slugify(f"tenant:{row.tenant_name}:{row.property_name}")
    lease_id = slugify(f"lease:{row.tenant_name}:{row.property_name}:{row.unit_number or 'main'}")

    tenant_status = _TENANT_STATUS_MAP.get(
        row.tenant_status.strip().lower(), TenantStatus.CURRENT,
    )
    tags: list[str] = [t.strip() for t in (row.tags or "").split(",") if t.strip()]
    last_payment: date | None = row.last_payment_date.date() if row.last_payment_date else None

    return _DomainModels(
        prop_id=prop_id,
        prop_name=row.property_name,
        prop_address=row.property_address,
        unit=Unit(
            id=unit_id,
            property_id=prop_id,
            unit_number=row.unit_number or "main",
            status=UnitStatus.OCCUPIED,
            occupancy_status=OccupancyStatus.OCCUPIED,
            current_rent=Decimal(str(row.monthly_rent)) if row.monthly_rent else Decimal("0"),
            source_document_id=doc_id,
        ),
        tenant=Tenant(
            id=tenant_id,
            name=row.tenant_name,
            status=tenant_status,
            balance_owed=Decimal(str(row.amount_owed)),
            balance_0_30=Decimal(str(row.balance_0_30)),
            balance_30_plus=Decimal(str(row.balance_30_plus)),
            last_payment_date=last_payment,
            tags=tags,
            source_document_id=doc_id,
        ),
        lease=Lease(
            id=lease_id,
            unit_id=unit_id,
            tenant_id=tenant_id,
            property_id=prop_id,
            start_date=date(2000, 1, 1),
            end_date=date(2099, 12, 31),
            monthly_rent=Decimal(str(row.monthly_rent)) if row.monthly_rent else Decimal("0"),
            source_document_id=doc_id,
        ),
    )


# -- Lease Expiration --

def _lease_exp_kb_entities(
    row: LeaseExpirationRow, namespace: str, doc_id: str,
) -> list[_KBEntity]:
    prop_id = slugify(f"property:{row.property_name}")
    unit_id = slugify(f"unit:{row.property_name}:{row.unit_number or 'main'}")
    tenant_id = slugify(f"tenant:{row.tenant_name}:{row.property_name}")

    prop_props: dict[str, Any] = {
        "address": row.property_address,
        "name": row.property_name,
        "source_doc": doc_id,
    }
    if row.tags:
        prop_props["manager_tag"] = row.tags

    unit_kb_props: dict[str, Any] = {
        "property_name": row.property_name,
        "unit_number": row.unit_number,
        "monthly_rent": row.monthly_rent,
        "source_doc": doc_id,
    }
    if row.market_rent:
        unit_kb_props["market_rent"] = row.market_rent
    if row.sqft:
        unit_kb_props["sqft"] = row.sqft

    tenant_kb_props: dict[str, Any] = {
        "name": row.tenant_name,
        "monthly_rent": row.monthly_rent,
        "deposit": row.deposit,
        "is_month_to_month": row.is_month_to_month,
        "source_doc": doc_id,
    }
    if row.move_in_date:
        tenant_kb_props["move_in_date"] = row.move_in_date.isoformat()
    if row.lease_expires:
        tenant_kb_props["lease_expires"] = row.lease_expires.isoformat()
    if row.phone_numbers:
        tenant_kb_props["phone_numbers"] = row.phone_numbers

    return [
        _KBEntity(entity_id=prop_id, entity_type="appfolio_property", properties=prop_props),
        _KBEntity(entity_id=unit_id, entity_type="appfolio_unit", properties=unit_kb_props),
        _KBEntity(entity_id=tenant_id, entity_type="appfolio_tenant", properties=tenant_kb_props),
    ]


def _lease_exp_kb_rels(row: LeaseExpirationRow, namespace: str) -> list[_KBRelationship]:
    prop_id = slugify(f"property:{row.property_name}")
    unit_id = slugify(f"unit:{row.property_name}:{row.unit_number or 'main'}")
    tenant_id = slugify(f"tenant:{row.tenant_name}:{row.property_name}")
    return [
        _KBRelationship(source_id=unit_id, target_id=prop_id, relation_type="belongs_to"),
        _KBRelationship(source_id=tenant_id, target_id=unit_id, relation_type="leases"),
    ]


def _lease_exp_domain(
    row: LeaseExpirationRow, doc_id: str, portfolio_id: str | None,
) -> _DomainModels:
    prop_id = slugify(f"property:{row.property_name}")
    unit_id = slugify(f"unit:{row.property_name}:{row.unit_number or 'main'}")
    tenant_id = slugify(f"tenant:{row.tenant_name}:{row.property_name}")
    lease_id = slugify(f"lease:{row.tenant_name}:{row.property_name}:{row.unit_number or 'main'}")

    has_active_lease = row.monthly_rent > 0 and row.tenant_name.strip() != ""
    unit_status = UnitStatus.OCCUPIED if has_active_lease else UnitStatus.VACANT
    occ_status = OccupancyStatus.OCCUPIED if has_active_lease else None

    start = row.move_in_date.date() if row.move_in_date else date(2000, 1, 1)
    end = row.lease_expires.date() if row.lease_expires else date(2099, 12, 31)

    return _DomainModels(
        prop_id=prop_id,
        prop_name=row.property_name,
        prop_address=row.property_address,
        unit=Unit(
            id=unit_id,
            property_id=prop_id,
            unit_number=row.unit_number or "main",
            sqft=row.sqft,
            current_rent=Decimal(str(row.monthly_rent)),
            market_rent=Decimal(str(row.market_rent)) if row.market_rent else Decimal("0"),
            status=unit_status,
            occupancy_status=occ_status,
            source_document_id=doc_id,
        ),
        tenant=Tenant(
            id=tenant_id,
            name=row.tenant_name,
            phone=row.phone_numbers,
            source_document_id=doc_id,
        ),
        lease=Lease(
            id=lease_id,
            unit_id=unit_id,
            tenant_id=tenant_id,
            property_id=prop_id,
            start_date=start,
            end_date=end,
            monthly_rent=Decimal(str(row.monthly_rent)),
            deposit=Decimal(str(row.deposit)),
            market_rent=Decimal(str(row.market_rent)) if row.market_rent else Decimal("0"),
            is_month_to_month=row.is_month_to_month,
            source_document_id=doc_id,
        ),
    )


# -- Property Directory --

_PROPERTY_COL_CANDIDATES = ["Property", "Property Name", "Building", "Address", "Location"]
_MANAGER_COL_CANDIDATES = [
    "Site Manager Name", "Property Manager", "Manager", "Managed By", "PM", "Tags",
]
_ADDRESS_COL_CANDIDATES = ["Address", "Full Address", "Street", "Property Address"]
_STATUS_COL_CANDIDATES = ["Status", "Active", "Property Status"]

_SKIP_PATTERNS = ("do not use", "admin", "test property")


def _first_match(row: dict[str, Any], candidates: list[str]) -> str | None:
    for key in candidates:
        if key in row and row[key] is not None:
            val = str(row[key]).strip()
            if val:
                return val
    return None


def _parse_property_directory_rows(raw_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Property directory has no typed parse function — pass raw rows through
    after filtering out junk rows."""
    results: list[dict[str, Any]] = []
    for row in raw_rows:
        prop_raw = _first_match(row, _PROPERTY_COL_CANDIDATES)
        if not prop_raw:
            continue
        prop_name = parse_property_name(prop_raw)
        if any(pat in prop_name.lower() for pat in _SKIP_PATTERNS):
            continue
        results.append(row)
    return results


def _prop_dir_kb_entities(
    row: dict[str, Any], namespace: str, doc_id: str,
) -> list[_KBEntity]:
    prop_raw = _first_match(row, _PROPERTY_COL_CANDIDATES) or ""
    prop_name = parse_property_name(prop_raw)
    prop_id = slugify(f"property:{prop_name}")
    addr_raw = _first_match(row, _ADDRESS_COL_CANDIDATES) or prop_raw
    manager_raw = _first_match(row, _MANAGER_COL_CANDIDATES)

    props: dict[str, Any] = {
        "name": prop_name,
        "address": addr_raw,
        "source_doc": doc_id,
    }
    if manager_raw:
        props["manager_tag"] = manager_raw
    status = _first_match(row, _STATUS_COL_CANDIDATES)
    if status:
        props["status"] = status

    return [_KBEntity(entity_id=prop_id, entity_type="appfolio_property", properties=props)]


def _prop_dir_kb_rels(row: dict[str, Any], namespace: str) -> list[_KBRelationship]:
    return []


def _prop_dir_domain(
    row: dict[str, Any], doc_id: str, portfolio_id: str | None,
) -> _DomainModels:
    prop_raw = _first_match(row, _PROPERTY_COL_CANDIDATES) or ""
    prop_name = parse_property_name(prop_raw)
    prop_id = slugify(f"property:{prop_name}")
    addr_raw = _first_match(row, _ADDRESS_COL_CANDIDATES) or prop_raw
    return _DomainModels(
        prop_id=prop_id,
        prop_name=prop_name,
        prop_address=addr_raw,
    )


def _prop_dir_get_manager_tag(row: dict[str, Any]) -> str | None:
    return _first_match(row, _MANAGER_COL_CANDIDATES)


# ---------------------------------------------------------------------------
# Manager tag extraction functions per report type
# ---------------------------------------------------------------------------

def _get_manager_tag_from_tags_field(row: Any) -> str | None:
    """For delinquency/lease_expiration: extract from the typed row's .tags field."""
    tags = getattr(row, "tags", None)
    return tags


def _get_manager_tag_noop(row: Any) -> str | None:
    return None


# ---------------------------------------------------------------------------
# Schema registry
# ---------------------------------------------------------------------------

REPORT_SCHEMAS: dict[str, ReportSchema] = {
    AppFolioReportType.RENT_ROLL: ReportSchema(
        report_type=AppFolioReportType.RENT_ROLL,
        parse_fn=parse_rent_roll_rows,
        manager_extraction=ManagerExtraction.NONE,
        manager_field=None,
        scoped_replace=True,
        produces_units=True,
        produces_tenants=False,
        produces_leases=False,
        extract_kb_entities=_rent_roll_kb_entities,
        extract_kb_relationships=_rent_roll_kb_rels,
        extract_domain_models=_rent_roll_domain,
    ),
    AppFolioReportType.DELINQUENCY: ReportSchema(
        report_type=AppFolioReportType.DELINQUENCY,
        parse_fn=parse_delinquency_rows,
        manager_extraction=ManagerExtraction.NONE,
        manager_field=None,
        scoped_replace=True,
        produces_units=True,
        produces_tenants=True,
        produces_leases=True,
        extract_kb_entities=_delinquency_kb_entities,
        extract_kb_relationships=_delinquency_kb_rels,
        extract_domain_models=_delinquency_domain,
    ),
    AppFolioReportType.LEASE_EXPIRATION: ReportSchema(
        report_type=AppFolioReportType.LEASE_EXPIRATION,
        parse_fn=parse_lease_expiration_rows,
        manager_extraction=ManagerExtraction.NONE,
        manager_field=None,
        scoped_replace=False,
        produces_units=True,
        produces_tenants=True,
        produces_leases=True,
        extract_kb_entities=_lease_exp_kb_entities,
        extract_kb_relationships=_lease_exp_kb_rels,
        extract_domain_models=_lease_exp_domain,
    ),
    AppFolioReportType.PROPERTY_DIRECTORY: ReportSchema(
        report_type=AppFolioReportType.PROPERTY_DIRECTORY,
        parse_fn=_parse_property_directory_rows,
        manager_extraction=ManagerExtraction.DIRECT,
        manager_field="_property_directory",
        scoped_replace=False,
        produces_units=False,
        produces_tenants=False,
        produces_leases=False,
        extract_kb_entities=_prop_dir_kb_entities,
        extract_kb_relationships=_prop_dir_kb_rels,
        extract_domain_models=_prop_dir_domain,
    ),
}


# ---------------------------------------------------------------------------
# Unified ingestion loop
# ---------------------------------------------------------------------------

def _get_row_manager_tag(row: Any, schema: ReportSchema) -> str | None:
    """Extract the raw manager tag value from a row according to the schema."""
    if schema.manager_extraction == ManagerExtraction.NONE:
        return None

    if schema.manager_field == "_property_directory":
        return _prop_dir_get_manager_tag(row)

    raw = getattr(row, schema.manager_field, None) if schema.manager_field else None
    return extract_manager_tag(raw, schema.manager_extraction)


def _get_row_property_id(row: Any, schema: ReportSchema) -> str:
    """Derive the property ID from a row."""
    if schema.manager_field == "_property_directory":
        prop_raw = _first_match(row, _PROPERTY_COL_CANDIDATES) or ""
        return slugify(f"property:{parse_property_name(prop_raw)}")
    return slugify(f"property:{row.property_name}")


async def ingest_report(
    doc_id: str,
    rows: list[dict[str, Any]],
    namespace: str,
    schema: ReportSchema,
    kb: KnowledgeStore,
    ps: PropertyStore,
    manager_resolver: ManagerResolver,
    result: IngestionResult,
    upload_portfolio_id: str | None = None,
) -> None:
    """Unified ingestion: parse, classify managers, create entities and domain models."""
    parsed_rows = schema.parse_fn(rows)

    if not parsed_rows:
        logger.warning("ingest_report_empty", doc_id=doc_id, report_type=schema.report_type)
        return

    # --- Scoped replace: clear stale units/leases ---
    if schema.scoped_replace:
        affected: set[str] = set()
        for row in parsed_rows:
            affected.add(_get_row_property_id(row, schema))
        for prop_id in affected:
            deleted_units = await ps.delete_units_by_property(prop_id)
            deleted_leases = await ps.delete_leases_by_property(prop_id)
            if deleted_units or deleted_leases:
                logger.info(
                    "scoped_replace_cleared",
                    property_id=prop_id,
                    units_removed=deleted_units,
                    leases_removed=deleted_leases,
                    source_doc=doc_id,
                )

    # Build per-property manager tag map (first non-empty tag per property).
    # Frequency classification counts *distinct properties* per tag value,
    # not raw row occurrences — "Section 8" on 18 tenants at 2 properties
    # is still only 2 properties.
    prop_manager_tag: dict[str, str] = {}
    for row in parsed_rows:
        prop_id = _get_row_property_id(row, schema)
        if prop_id not in prop_manager_tag:
            tag = _get_row_manager_tag(row, schema)
            if tag:
                prop_manager_tag[prop_id] = tag

    real_managers = classify_manager_values(prop_manager_tag)

    # --- Row-by-row ingestion ---
    for row in parsed_rows:
        # KB entities
        kb_entities = schema.extract_kb_entities(row, namespace, doc_id)
        for ent in kb_entities:
            existing = await kb.get_entity(namespace, ent.entity_id)
            if existing:
                merged = {**existing.properties, **ent.properties}
                await kb.put_entity(
                    Entity(
                        entity_id=ent.entity_id,
                        entity_type=ent.entity_type,
                        namespace=namespace,
                        properties=merged,
                    )
                )
            else:
                await kb.put_entity(
                    Entity(
                        entity_id=ent.entity_id,
                        entity_type=ent.entity_type,
                        namespace=namespace,
                        properties=ent.properties,
                    )
                )
                result.entities_created += 1

        # KB relationships
        kb_rels = schema.extract_kb_relationships(row, namespace)
        for rel in kb_rels:
            await kb.put_relationship(
                Relationship(
                    source_id=rel.source_id,
                    target_id=rel.target_id,
                    relation_type=rel.relation_type,
                    namespace=namespace,
                )
            )
            result.relationships_created += 1

        # Manager resolution
        prop_id = _get_row_property_id(row, schema)
        portfolio_id: str | None = upload_portfolio_id
        if portfolio_id is None:
            manager_tag = prop_manager_tag.get(prop_id)
            if manager_tag and manager_tag in real_managers:
                portfolio_id = await manager_resolver.ensure_manager(manager_tag)
            elif manager_tag:
                result.manager_tags_skipped.append(manager_tag)

        # Domain models
        domain = schema.extract_domain_models(row, doc_id, portfolio_id)
        addr = parse_address(domain.prop_address)

        existing_prop = await ps.get_property(domain.prop_id)
        if portfolio_id is not None:
            effective_pid = portfolio_id
        elif existing_prop is not None and existing_prop.portfolio_id:
            effective_pid = existing_prop.portfolio_id
        else:
            effective_pid = ""

        await ps.upsert_property(
            Property(
                id=domain.prop_id,
                portfolio_id=effective_pid,
                name=domain.prop_name,
                address=addr,
                source_document_id=doc_id,
            )
        )

        if domain.unit:
            await ps.upsert_unit(domain.unit)
        if domain.tenant:
            await ps.upsert_tenant(domain.tenant)
        if domain.lease:
            await ps.upsert_lease(domain.lease)

    logger.info(
        "ingest_report_complete",
        doc_id=doc_id,
        report_type=schema.report_type,
        rows=len(parsed_rows),
        real_managers=len(real_managers),
        tags_skipped=len(result.manager_tags_skipped),
    )
