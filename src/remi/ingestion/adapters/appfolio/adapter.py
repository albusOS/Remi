"""AppFolio adapter — public entry point for AppFolio document parsing.

``parse(doc)`` is the only public function.  It detects the report type,
dispatches to the appropriate row parser, and maps every row to one or more
canonical ``IngestionEvent`` instances.

All AppFolio-specific knowledge lives here and in the sibling modules:
  - Magic section header strings (rent roll occupancy sections)
  - Skip patterns for junk property names
  - "month-to-month" special-casing
  - Column candidate lists for property directory
  - Occupancy / tenant status string maps
  - Delinquency unit forced-occupied convention
  - Lease expiration active-lease heuristic

Nothing outside this package needs to know any of the above.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import structlog

from remi.ingestion.events import (
    IngestionEvent,
    LeaseObserved,
    ManagerObserved,
    PropertyObserved,
    ScopeReplace,
    SourceRef,
    TenantObserved,
    UnitObserved,
)
from remi.types.text import slugify
from remi.ingestion.adapters.appfolio.detector import detect_report_type_scored
from remi.ingestion.adapters.appfolio.parsers import (
    DelinquencyRow,
    LeaseExpirationRow,
    RentRollRow,
    parse_delinquency_rows,
    parse_lease_expiration_rows,
    parse_property_name,
    parse_rent_roll_rows,
)
from remi.ingestion.adapters.appfolio.schema import AppFolioReportType
from remi.portfolio.models import (
    Address,
    LeaseStatus,
    OccupancyStatus,
    TenantStatus,
    UnitStatus,
)

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Occupancy / tenant status maps (AppFolio strings → canonical enums)
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

# Property names that should be ignored across all report types
_SKIP_PATTERNS: tuple[str, ...] = ("do not use", "admin", "test property")

# Property directory: candidate column names for flexible-layout reports
_PROPERTY_COL_CANDIDATES = ["Property", "Property Name", "Building", "Address", "Location"]
_MANAGER_COL_CANDIDATES = [
    "Site Manager Name", "Property Manager", "Manager", "Managed By", "PM", "Tags",
]
_ADDRESS_COL_CANDIDATES = ["Address", "Full Address", "Street", "Property Address"]


# ---------------------------------------------------------------------------
# Address / occupancy helpers — inlined to avoid importing through the
# knowledge/ingestion package (which would trigger a circular import via its
# __init__.py loading IngestionService → adapters.registry → this module).
# ---------------------------------------------------------------------------


def _parse_address(full_address: str) -> Address:
    """Best-effort address parsing from AppFolio's combined address string."""
    name = parse_property_name(full_address)
    parts = full_address.rsplit(",", 1)
    city = "Pittsburgh"
    state = "PA"
    zip_code = ""
    if len(parts) >= 2:
        tail = parts[1].strip()
        state_zip = tail.split()
        if len(state_zip) >= 2:
            state = state_zip[0]
            zip_code = state_zip[1]
        elif len(state_zip) == 1:
            state = state_zip[0]
    return Address(street=name, city=city, state=state, zip_code=zip_code)


def _occupancy_to_unit_status(occ: OccupancyStatus | None) -> UnitStatus:
    """Map AppFolio occupancy granularity to the simpler UnitStatus enum."""
    if occ is None:
        return UnitStatus.VACANT
    if occ in (
        OccupancyStatus.OCCUPIED,
        OccupancyStatus.NOTICE_RENTED,
        OccupancyStatus.NOTICE_UNRENTED,
    ):
        return UnitStatus.OCCUPIED
    return UnitStatus.VACANT


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


def parse(doc_id: str, column_names: list[str], rows: list[dict[str, Any]]) -> list[IngestionEvent]:
    """Parse an AppFolio document into canonical IngestionEvents.

    Returns an empty list when the document is not a recognised AppFolio
    report type (caller should fall back to generic ingest or LLM enrichment).
    """
    report_type, confidence = detect_report_type_scored(column_names)
    logger.debug(
        "appfolio_adapter_detected",
        doc_id=doc_id,
        report_type=report_type,
        confidence=confidence,
    )

    if report_type == AppFolioReportType.RENT_ROLL:
        return _from_rent_roll(parse_rent_roll_rows(rows), doc_id)
    if report_type == AppFolioReportType.DELINQUENCY:
        return _from_delinquency(parse_delinquency_rows(rows), doc_id)
    if report_type == AppFolioReportType.LEASE_EXPIRATION:
        return _from_lease_expiration(parse_lease_expiration_rows(rows), doc_id)
    if report_type == AppFolioReportType.PROPERTY_DIRECTORY:
        return _from_property_directory(rows, doc_id)
    return []


# ---------------------------------------------------------------------------
# Per-report mappers
# ---------------------------------------------------------------------------


def _source(report_type: str, doc_id: str) -> SourceRef:
    return SourceRef(platform="appfolio", report_type=report_type, doc_id=doc_id)


def _skip_property(name: str) -> bool:
    low = name.lower()
    return any(pat in low for pat in _SKIP_PATTERNS)


def _from_rent_roll(rows: list[RentRollRow], doc_id: str) -> list[IngestionEvent]:
    source = _source(AppFolioReportType.RENT_ROLL, doc_id)
    events: list[IngestionEvent] = []
    seen_properties: set[str] = set()

    for row in rows:
        if _skip_property(row.property_name):
            continue

        prop_id = slugify(f"property:{row.property_name}")
        unit_id = slugify(f"unit:{row.property_name}:{row.unit_number or 'main'}")

        if prop_id not in seen_properties:
            seen_properties.add(prop_id)
            events.append(
                ScopeReplace(
                    property_id=prop_id,
                    replace_units=True,
                    replace_leases=False,
                    source=source,
                )
            )
            events.append(
                PropertyObserved(
                    property_id=prop_id,
                    name=row.property_name,
                    address=_parse_address(row.property_address),
                    portfolio_id=None,
                    source=source,
                )
            )

        occupancy = _OCCUPANCY_MAP.get(row.occupancy_status)
        unit_status = _occupancy_to_unit_status(occupancy)

        events.append(
            UnitObserved(
                unit_id=unit_id,
                property_id=prop_id,
                unit_number=row.unit_number or "main",
                status=unit_status,
                occupancy_status=occupancy,
                bedrooms=row.bedrooms,
                bathrooms=row.bathrooms,
                sqft=None,
                market_rent=Decimal("0"),
                current_rent=Decimal("0"),
                days_vacant=row.days_vacant,
                listed_on_website=row.posted_website,
                listed_on_internet=row.posted_internet,
                source=source,
            )
        )

    return events


def _from_delinquency(rows: list[DelinquencyRow], doc_id: str) -> list[IngestionEvent]:
    source = _source(AppFolioReportType.DELINQUENCY, doc_id)
    events: list[IngestionEvent] = []
    seen_properties: set[str] = set()

    for row in rows:
        if _skip_property(row.property_name):
            continue

        prop_id = slugify(f"property:{row.property_name}")
        unit_id = slugify(f"unit:{row.property_name}:{row.unit_number or 'main'}")
        tenant_id = slugify(f"tenant:{row.tenant_name}:{row.property_name}")
        lease_id = slugify(
            f"lease:{row.tenant_name}:{row.property_name}:{row.unit_number or 'main'}"
        )

        if prop_id not in seen_properties:
            seen_properties.add(prop_id)
            events.append(
                ScopeReplace(
                    property_id=prop_id,
                    replace_units=True,
                    replace_leases=True,
                    source=source,
                )
            )
            events.append(
                PropertyObserved(
                    property_id=prop_id,
                    name=row.property_name,
                    address=_parse_address(row.property_address),
                    portfolio_id=None,
                    source=source,
                )
            )

        # Emit manager tag from the tags field (first comma segment, skip MTM)
        if row.tags:
            tag_segment = row.tags.strip().split(",")[0].strip()
            if tag_segment and tag_segment.lower() != "month-to-month":
                events.append(
                    ManagerObserved(
                        manager_tag=tag_segment,
                        property_id=prop_id,
                        source=source,
                    )
                )

        events.append(
            UnitObserved(
                unit_id=unit_id,
                property_id=prop_id,
                unit_number=row.unit_number or "main",
                status=UnitStatus.OCCUPIED,
                occupancy_status=OccupancyStatus.OCCUPIED,
                bedrooms=None,
                bathrooms=None,
                sqft=None,
                market_rent=Decimal("0"),
                current_rent=Decimal(str(row.monthly_rent)) if row.monthly_rent else Decimal("0"),
                days_vacant=None,
                listed_on_website=False,
                listed_on_internet=False,
                source=source,
            )
        )

        tenant_status = _TENANT_STATUS_MAP.get(
            row.tenant_status.strip().lower(), TenantStatus.CURRENT
        )
        tags: list[str] = [t.strip() for t in (row.tags or "").split(",") if t.strip()]

        events.append(
            TenantObserved(
                tenant_id=tenant_id,
                name=row.tenant_name,
                status=tenant_status,
                balance_owed=Decimal(str(row.amount_owed)),
                balance_0_30=Decimal(str(row.balance_0_30)),
                balance_30_plus=Decimal(str(row.balance_30_plus)),
                last_payment_date=row.last_payment_date,
                tags=tags,
                phone=None,
                source=source,
            )
        )

        # Delinquency reports do not carry real lease dates.  Emit LeaseObserved
        # with None dates so the engine can create a minimal lease record without
        # using fake sentinel values.
        events.append(
            LeaseObserved(
                lease_id=lease_id,
                unit_id=unit_id,
                tenant_id=tenant_id,
                property_id=prop_id,
                start_date=None,
                end_date=None,
                monthly_rent=Decimal(str(row.monthly_rent)) if row.monthly_rent else Decimal("0"),
                market_rent=Decimal("0"),
                deposit=Decimal("0"),
                is_month_to_month=False,
                status=LeaseStatus.ACTIVE,
                source=source,
            )
        )

    return events


def _from_lease_expiration(rows: list[LeaseExpirationRow], doc_id: str) -> list[IngestionEvent]:
    source = _source(AppFolioReportType.LEASE_EXPIRATION, doc_id)
    events: list[IngestionEvent] = []
    seen_properties: set[str] = set()

    for row in rows:
        if _skip_property(row.property_name):
            continue

        prop_id = slugify(f"property:{row.property_name}")
        unit_id = slugify(f"unit:{row.property_name}:{row.unit_number or 'main'}")
        tenant_id = slugify(f"tenant:{row.tenant_name}:{row.property_name}")
        lease_id = slugify(
            f"lease:{row.tenant_name}:{row.property_name}:{row.unit_number or 'main'}"
        )

        if prop_id not in seen_properties:
            seen_properties.add(prop_id)
            events.append(
                PropertyObserved(
                    property_id=prop_id,
                    name=row.property_name,
                    address=_parse_address(row.property_address),
                    portfolio_id=None,
                    source=source,
                )
            )

        # Manager tag lives in the tags field for lease expiration rows
        if row.tags and row.tags.strip().lower() != "month-to-month":
            events.append(
                ManagerObserved(
                    manager_tag=row.tags.strip(),
                    property_id=prop_id,
                    source=source,
                )
            )

        has_active_lease = row.monthly_rent > 0 and row.tenant_name.strip() != ""
        unit_status = UnitStatus.OCCUPIED if has_active_lease else UnitStatus.VACANT
        occupancy = OccupancyStatus.OCCUPIED if has_active_lease else None

        events.append(
            UnitObserved(
                unit_id=unit_id,
                property_id=prop_id,
                unit_number=row.unit_number or "main",
                status=unit_status,
                occupancy_status=occupancy,
                bedrooms=None,
                bathrooms=None,
                sqft=row.sqft,
                market_rent=Decimal(str(row.market_rent)) if row.market_rent else Decimal("0"),
                current_rent=Decimal(str(row.monthly_rent)),
                days_vacant=None,
                listed_on_website=False,
                listed_on_internet=False,
                source=source,
            )
        )

        events.append(
            TenantObserved(
                tenant_id=tenant_id,
                name=row.tenant_name,
                status=TenantStatus.CURRENT,
                balance_owed=Decimal("0"),
                balance_0_30=Decimal("0"),
                balance_30_plus=Decimal("0"),
                last_payment_date=None,
                tags=[],
                phone=row.phone_numbers,
                source=source,
            )
        )

        events.append(
            LeaseObserved(
                lease_id=lease_id,
                unit_id=unit_id,
                tenant_id=tenant_id,
                property_id=prop_id,
                start_date=row.move_in_date,
                end_date=row.lease_expires,
                monthly_rent=Decimal(str(row.monthly_rent)),
                market_rent=Decimal(str(row.market_rent)) if row.market_rent else Decimal("0"),
                deposit=Decimal(str(row.deposit)),
                is_month_to_month=row.is_month_to_month,
                status=LeaseStatus.ACTIVE,
                source=source,
            )
        )

    return events


def _first_match(row: dict[str, Any], candidates: list[str]) -> str | None:
    for key in candidates:
        if key in row and row[key] is not None:
            val = str(row[key]).strip()
            if val:
                return val
    return None


def _from_property_directory(raw_rows: list[dict[str, Any]], doc_id: str) -> list[IngestionEvent]:
    source = _source(AppFolioReportType.PROPERTY_DIRECTORY, doc_id)
    events: list[IngestionEvent] = []

    for row in raw_rows:
        prop_raw = _first_match(row, _PROPERTY_COL_CANDIDATES)
        if not prop_raw:
            continue

        prop_name = parse_property_name(prop_raw)
        if _skip_property(prop_name):
            continue

        prop_id = slugify(f"property:{prop_name}")
        addr_raw = _first_match(row, _ADDRESS_COL_CANDIDATES) or prop_raw

        events.append(
            PropertyObserved(
                property_id=prop_id,
                name=prop_name,
                address=_parse_address(addr_raw),
                portfolio_id=None,
                source=source,
            )
        )

        manager_raw = _first_match(row, _MANAGER_COL_CANDIDATES)
        if manager_raw:
            events.append(
                ManagerObserved(
                    manager_tag=manager_raw,
                    property_id=prop_id,
                    source=source,
                )
            )

    return events
