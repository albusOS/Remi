"""Pre-persistence row validation — check rows have enough data for persisters.

The persisters derive IDs and FK fields from human-readable data (address,
tenant name, unit number). This validator checks that the *source data*
needed by each persister is present — NOT the Pydantic model's required
fields, which include computed FKs.

Used by the orchestrator before handing rows to persisters.
"""

from __future__ import annotations

from typing import Any

import structlog

from remi.application.services.ingestion.base import IngestionResult, RowWarning
from remi.application.services.ingestion.resolver import PERSISTABLE_TYPES

_log = structlog.get_logger(__name__)

# What each persister actually needs from the mapped row to function.
# These are the human-readable columns that the LLM maps, not FK IDs.
_PERSISTER_REQUIREMENTS: dict[str, frozenset[str]] = {
    "Unit": frozenset({"property_address"}),
    "Tenant": frozenset({"property_address"}),
    "BalanceObservation": frozenset({"property_address"}),
    "Lease": frozenset({"property_address"}),
    "Property": frozenset({"property_address"}),
    "MaintenanceRequest": frozenset({"property_address"}),
    "Owner": frozenset(),
    "Vendor": frozenset(),
    "PropertyManager": frozenset(),
}


def validate_rows(
    rows: list[dict[str, Any]],
    result: IngestionResult,
) -> list[dict[str, Any]]:
    """Validate mapped rows have the data persisters need.

    Returns only the accepted rows. Appends ``RowWarning`` entries to
    *result* for each rejected row and increments the appropriate counters.
    """
    accepted: list[dict[str, Any]] = []

    for idx, row in enumerate(rows):
        entity_type = row.get("type", "")

        if entity_type not in PERSISTABLE_TYPES:
            result.observation_rows.append(row)
            result.rows_skipped += 1
            continue

        required = _PERSISTER_REQUIREMENTS.get(entity_type, frozenset())
        missing = [f for f in required if not _has_value(row, f)]

        if missing:
            for field_name in missing:
                result.validation_warnings.append(
                    RowWarning(
                        row_index=idx,
                        row_type=entity_type,
                        field=field_name,
                        issue="required source field missing",
                        raw_value="",
                    )
                )
            result.rows_rejected += 1

            _log.info(
                "row_rejected",
                row_index=idx,
                entity_type=entity_type,
                missing_fields=missing,
            )
            continue

        accepted.append(row)
        result.rows_accepted += 1

    return accepted


def _has_value(row: dict[str, Any], field: str) -> bool:
    """Check if a row has a non-empty value for a field.

    Also checks common aliases — e.g. ``property_address`` can be
    satisfied by ``address``, ``property_name``, or a section header.
    """
    if field == "property_address":
        for key in ("property_address", "address", "property_name", "_section_header"):
            val = row.get(key)
            if val is not None and str(val).strip():
                return True
        return False

    val = row.get(field)
    return val is not None and str(val).strip() != ""
