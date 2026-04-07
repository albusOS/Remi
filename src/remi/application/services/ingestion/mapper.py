"""Column-map application — the convergence point for all classification paths.

Both the algorithmic matcher and the LLM extract step produce the same
shape: a ``column_map: dict[str, str]`` from raw column names to ontology
field names. This module applies that map to raw rows with full hygiene:

  - Rename columns using the map
  - Propagate section context (``_ctx_property_address``) into ``property_address``
  - Normalize addresses via ``rules.normalize_address``
  - Filter junk properties via ``rules.is_junk_property``
  - Skip section header rows via ``rules.is_section_header``
  - Split ``_bd_ba`` fields via ``rules.split_bd_ba``
  - Attach ``type: entity_type`` to every output row
  - Unmapped columns go into ``extra_fields`` dict

This is the single function that makes 200 report types manageable: the
classification strategy varies, but the row-level hygiene is always the same.
"""

from __future__ import annotations

from typing import Any

import structlog

from remi.application.services.ingestion.rules import (
    is_junk_property,
    is_section_header,
    normalize_address,
    split_bd_ba,
)

_log = structlog.get_logger(__name__)


def apply_column_map(
    rows: list[dict[str, Any]],
    column_map: dict[str, str],
    entity_type: str,
    *,
    section_header_column: str | None = None,
) -> list[dict[str, Any]]:
    """Apply a column map to raw rows, producing ontology-aligned mapped rows.

    *column_map* maps raw column names to canonical field names.
    *entity_type* is attached as ``type`` on every output row.
    *section_header_column* is the raw column whose value encodes section
    context in hierarchical reports (e.g. "Property" column in AppFolio rent
    rolls). When set, rows with only that column populated are treated as
    section headers that set context for subsequent rows.
    """
    mapped: list[dict[str, Any]] = []
    current_property: str | None = None
    current_section: str | None = None
    total_skipped = 0

    for raw_row in rows:
        out: dict[str, Any] = {"type": entity_type}
        extra: dict[str, Any] = {}

        for raw_col, val in raw_row.items():
            # Carry through parser-injected context fields
            if raw_col.startswith("_ctx_"):
                out[raw_col] = val
                continue

            if val is None:
                continue
            val_str = str(val).strip()
            if not val_str:
                continue

            mapped_field = column_map.get(raw_col)
            if mapped_field:
                out[mapped_field] = val
            else:
                extra[raw_col] = val

        if extra:
            out["extra_fields"] = extra

        # --- BD/BA splitting ---
        bd_ba = out.pop("_bd_ba", None)
        if bd_ba is not None:
            beds, baths = split_bd_ba(str(bd_ba))
            if beds is not None and "bedrooms" not in out:
                out["bedrooms"] = beds
            if baths is not None and "bathrooms" not in out:
                out["bathrooms"] = baths

        # --- Section context propagation ---
        # Use parser-injected context first, fall back to section_header_column
        ctx_prop = out.pop("_ctx_property_address", None)
        ctx_section = out.pop("_ctx_section_label", None)
        if ctx_prop:
            current_property = str(ctx_prop)
        if ctx_section:
            current_section = str(ctx_section)

        # --- Address hygiene ---
        prop_val = str(out.get("property_address") or "").strip()
        if prop_val:
            normalized = normalize_address(prop_val)
            if is_section_header(out):
                current_property = normalized
                total_skipped += 1
                continue
            if is_junk_property(normalized):
                total_skipped += 1
                continue
            out["property_address"] = normalized
            current_property = normalized
        elif current_property:
            if is_junk_property(current_property):
                total_skipped += 1
                continue
            out["property_address"] = current_property

        # Attach section label if present
        if current_section:
            out.setdefault("_section_label", current_section)

        # Only emit rows with at least one meaningful data field
        has_data = any(
            k not in ("type", "extra_fields", "_section_label") and v is not None
            for k, v in out.items()
        )
        if not has_data:
            total_skipped += 1
            continue

        mapped.append(out)

    if total_skipped:
        _log.info(
            "mapper_skipped_rows",
            entity_type=entity_type,
            skipped=total_skipped,
            accepted=len(mapped),
        )

    return mapped
