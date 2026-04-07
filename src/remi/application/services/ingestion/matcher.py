"""Algorithmic column-to-entity matching against the ontology.

Scores each column header against every field in every known entity type
using token overlap, synonym expansion, and data-type heuristics. Picks
the entity type with the best aggregate coverage score. Zero LLM calls.

Sits between the rule engine (exact header signatures) and the LLM
pipeline (expensive, last resort). Handles the 80%+ of custom reports
where column names are close enough to ontology field names.
"""

from __future__ import annotations

import re
from typing import Any

import structlog

from remi.agent.graph import ObjectTypeDef
from remi.agent.graph.retrieval.introspect import pydantic_to_type_defs, schemas_for_prompt
from remi.application.core.models import (
    BalanceObservation,
    Lease,
    MaintenanceRequest,
    Owner,
    Property,
    PropertyManager,
    Tenant,
    Unit,
    Vendor,
)
from remi.application.core.models.enums import ReportType
from remi.application.services.ingestion.resolver import PERSISTABLE_TYPES

_ALL_TYPE_DEFS: list[ObjectTypeDef] = pydantic_to_type_defs([
    (PropertyManager, "Person or company managing one or more properties"),
    (Property, "A real-estate asset"),
    (Unit, "A rentable unit within a property"),
    (Lease, "A rental agreement"),
    (Tenant, "An individual or entity renting a unit"),
    (MaintenanceRequest, "A work order"),
    (BalanceObservation, "A point-in-time balance snapshot"),
    (Vendor, "A service provider"),
    (Owner, "A property owner"),
])

_log = structlog.get_logger(__name__)


def entity_schemas_for_prompt() -> str:
    """Render core RE entity schemas as structured text for LLM prompts."""
    return schemas_for_prompt(_ALL_TYPE_DEFS)

# ---------------------------------------------------------------------------
# Token normalization
# ---------------------------------------------------------------------------

_WORD_SPLIT_RE = re.compile(r"[_\s\-/]+")
_CAMEL_SPLIT_RE = re.compile(r"(?<=[a-z])(?=[A-Z])")


def _tokenize(name: str) -> list[str]:
    """Split a name into lowercase tokens on word boundaries."""
    expanded = _CAMEL_SPLIT_RE.sub(" ", name)
    return [t.lower().strip(".,:#()") for t in _WORD_SPLIT_RE.split(expanded) if t.strip()]


# ---------------------------------------------------------------------------
# Synonym table — maps common report column terms to ontology field tokens
# ---------------------------------------------------------------------------

_SYNONYMS: dict[str, list[str]] = {
    "property": ["property", "address", "building", "location"],
    "unit": ["unit", "apartment", "apt", "suite", "space"],
    "tenant": ["tenant", "resident", "occupant", "lessee", "renter"],
    "resident": ["tenant", "resident", "occupant", "renter"],
    "primary": ["primary", "main"],
    "name": ["name"],
    "rent": ["rent", "monthly"],
    "market": ["market"],
    "lease": ["lease", "agreement"],
    "from": ["start", "from", "begin"],
    "to": ["end", "to", "expires", "expiration"],
    "expires": ["end", "expires", "expiration"],
    "expiration": ["end", "expires", "expiration"],
    "status": ["status", "state"],
    "category": ["category", "type", "kind"],
    "priority": ["priority", "urgency", "severity"],
    "description": ["description", "notes", "details", "instructions", "summary", "job"],
    "job": ["description", "title", "job"],
    "title": ["title", "subject", "description", "job"],
    "vendor": ["vendor", "contractor", "provider", "assigned"],
    "cost": ["cost", "amount", "price", "total", "invoice"],
    "amount": ["amount", "cost", "total", "invoice"],
    "created": ["created", "opened", "requested", "submitted"],
    "completed": ["completed", "resolved", "closed", "done", "finished"],
    "scheduled": ["scheduled", "planned", "appointment"],
    "balance": ["balance", "owed", "receivable", "outstanding", "total"],
    "receivable": ["balance", "owed", "receivable", "outstanding"],
    "observed": ["observed", "reported", "recorded", "exported"],
    "total": ["total", "balance", "owed"],
    "sqft": ["sqft", "sq", "square", "feet", "area"],
    "beds": ["beds", "bedrooms", "bd"],
    "baths": ["baths", "bathrooms", "ba"],
    "phone": ["phone", "telephone", "mobile", "cell"],
    "email": ["email", "mail"],
    "deposit": ["deposit", "security"],
    "vacant": ["vacant", "vacancy"],
    "days": ["days"],
    "tags": ["tags", "labels"],
    "notes": ["notes", "description", "comments", "remarks"],
    "work": ["work", "maintenance", "order", "request"],
    "order": ["order", "work"],
    "issue": ["issue", "problem", "category"],
    "invoice": ["invoice", "cost", "bill"],
    "recurring": ["recurring", "repeat"],
    "manager": ["manager"],
    "site": ["site"],
    "owner": ["owner", "landlord"],
}


# Exact column-to-field overrides for unambiguous mappings that token
# matching struggles with. Checked before the fuzzy scoring loop.
_EXACT_OVERRIDES: dict[str, str] = {
    "completed on": "completed_date",
    "date completed": "completed_date",
    "work done on": "completed_date",
    "resolved": "resolved_at",
    "closed": "resolved_at",
    "scheduled start": "scheduled_date",
    "primary resident": "tenant_id",
    "tenant name": "tenant_id",
    "requested by": "tenant_id",
    "job description": "description",
    "work order issue": "category",
    "work order number": "title",
    "work order type": "source",
    "invoice amount": "cost",
}

# Cross-entity overrides — columns that carry context across entity boundaries
# (e.g. a rent roll row describes a Unit but also names the manager). These are
# always mapped regardless of the winning entity type's field list.
_CROSS_ENTITY_OVERRIDES: dict[str, str] = {
    "site manager name": "site_manager_name",
    "site manager": "site_manager_name",
    "property manager": "site_manager_name",
    "manager name": "site_manager_name",
    "managed by": "site_manager_name",
}


def _expand_synonyms(tokens: list[str]) -> set[str]:
    """Expand tokens using the synonym table."""
    expanded = set(tokens)
    for tok in tokens:
        if tok in _SYNONYMS:
            expanded.update(_SYNONYMS[tok])
    return expanded


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

_PROPERTY_ADDRESS_SIGNALS = frozenset(
    {
        "property",
        "address",
        "building",
        "location",
        "street",
    }
)


def _score_column_against_field(
    col_tokens: set[str],
    field_name: str,
    field_type: str,
) -> float:
    """Score how well a column matches a single entity field.

    Returns 0.0–1.0 where 1.0 is a perfect match.
    """
    field_tokens = set(_tokenize(field_name))

    exact = col_tokens & field_tokens
    if exact:
        return min(1.0, len(exact) / max(len(field_tokens), 1))

    col_expanded = _expand_synonyms(list(col_tokens))
    field_expanded = _expand_synonyms(list(field_tokens))
    overlap = col_expanded & field_expanded

    if overlap:
        union = col_expanded | field_expanded
        return len(overlap) / max(len(union), 1) * 0.8

    return 0.0


def _score_entity_type(
    columns: list[str],
    entity_def: ObjectTypeDef,
) -> tuple[float, dict[str, str], list[str]]:
    """Score how well a set of columns matches an entity type.

    Returns (score, column_map, unmatched_columns) where:
      - score: 0.0–1.0 aggregate coverage
      - column_map: {raw_column: ontology_field_name}
      - unmatched_columns: columns that didn't match any field
    """
    field_names = {p.name for p in entity_def.properties if p.name != "id"}
    field_defs = {p.name: p for p in entity_def.properties if p.name != "id"}

    column_map: dict[str, str] = {}
    matched_fields: set[str] = set()
    unmatched: list[str] = []

    # Pass 0: cross-entity overrides — always applied regardless of entity fields
    pre_remaining: list[str] = []
    for col in columns:
        col_lower = col.lower().strip()
        cross = _CROSS_ENTITY_OVERRIDES.get(col_lower)
        if cross:
            column_map[col] = cross
        else:
            pre_remaining.append(col)

    # Pass 1: exact overrides — highest confidence
    remaining_cols: list[str] = []
    for col in pre_remaining:
        col_lower = col.lower().strip()
        override = _EXACT_OVERRIDES.get(col_lower)
        if override and override in field_names and override not in matched_fields:
            column_map[col] = override
            matched_fields.add(override)
        else:
            remaining_cols.append(col)

    # Pass 2: property address detection
    still_remaining: list[str] = []
    for col in remaining_cols:
        col_toks = _expand_synonyms(_tokenize(col))
        if col_toks & _PROPERTY_ADDRESS_SIGNALS and "property_address" not in matched_fields:
            column_map[col] = "property_address"
            matched_fields.add("property_address")
        else:
            still_remaining.append(col)

    # Pass 3: fuzzy token matching for the rest
    for col in still_remaining:
        col_toks = _expand_synonyms(_tokenize(col))
        if not col_toks:
            unmatched.append(col)
            continue

        best_field: str | None = None
        best_score = 0.0

        for fname, fdef in field_defs.items():
            if fname in matched_fields:
                continue
            score = _score_column_against_field(col_toks, fname, fdef.data_type)
            if score > best_score:
                best_score = score
                best_field = fname

        if best_field and best_score >= 0.15:
            column_map[col] = best_field
            matched_fields.add(best_field)
        else:
            unmatched.append(col)

    field_count = len(field_defs)
    if field_count == 0:
        return 0.0, column_map, unmatched

    required_fields = {p.name for p in entity_def.required_properties() if p.name != "id"}
    required_matched = required_fields & matched_fields
    required_coverage = len(required_matched) / max(len(required_fields), 1)

    overall_coverage = len(matched_fields) / field_count
    column_utilization = len(column_map) / max(len(columns), 1)

    score = (required_coverage * 0.5) + (overall_coverage * 0.3) + (column_utilization * 0.2)

    # Penalise matches where most columns are unmatched — even perfect
    # required-field coverage shouldn't win when 60%+ of columns go unplaced.
    # Those columns likely belong to a different entity type.
    if column_utilization < 0.4:
        score *= column_utilization

    return score, column_map, unmatched


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class MatchResult:
    """Result of algorithmic column-to-entity matching."""

    __slots__ = ("entity_type", "score", "column_map", "unmatched_columns", "report_type")

    def __init__(
        self,
        entity_type: str,
        score: float,
        column_map: dict[str, str],
        unmatched_columns: list[str],
        report_type: ReportType,
    ) -> None:
        self.entity_type = entity_type
        self.score = score
        self.column_map = column_map
        self.unmatched_columns = unmatched_columns
        self.report_type = report_type


_ENTITY_TO_REPORT_TYPE: dict[str, ReportType] = {
    "Unit": ReportType.RENT_ROLL,
    "Tenant": ReportType.TENANT_DIRECTORY,
    "BalanceObservation": ReportType.DELINQUENCY,
    "Lease": ReportType.LEASE_EXPIRATION,
    "Property": ReportType.PROPERTY_DIRECTORY,
    "MaintenanceRequest": ReportType.WORK_ORDER,
    "Vendor": ReportType.VENDOR_DIRECTORY,
    "Owner": ReportType.OWNER_DIRECTORY,
    "PropertyManager": ReportType.MANAGER_DIRECTORY,
}

MIN_MATCH_SCORE = 0.20


def match_columns(columns: list[str]) -> MatchResult | None:
    """Match column headers to the best entity type from the ontology.

    Returns a MatchResult if a confident match is found, None otherwise.
    The caller can use the column_map to extract rows without an LLM call.
    """
    persistable_defs = [d for d in _ALL_TYPE_DEFS if d.name in PERSISTABLE_TYPES]

    best: MatchResult | None = None

    for entity_def in persistable_defs:
        score, col_map, unmatched = _score_entity_type(columns, entity_def)

        if score > (best.score if best else MIN_MATCH_SCORE):
            best = MatchResult(
                entity_type=entity_def.name,
                score=score,
                column_map=col_map,
                unmatched_columns=unmatched,
                report_type=_ENTITY_TO_REPORT_TYPE.get(entity_def.name, "unknown"),
            )

    if best:
        _log.info(
            "matcher_result",
            entity_type=best.entity_type,
            score=round(best.score, 3),
            mapped_columns=len(best.column_map),
            unmatched_columns=len(best.unmatched_columns),
        )

    return best


def apply_match(
    match: MatchResult,
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Apply a column match to raw rows, producing mapped rows.

    Translates column names to ontology field names using the match's
    column_map. Filters junk rows, section headers, and normalizes
    addresses — same hygiene as the LLM path's apply_column_map.
    """
    from remi.application.services.ingestion.rules import (
        is_junk_property,
        is_section_header,
        normalize_address,
    )

    mapped: list[dict[str, Any]] = []
    current_property: str | None = None

    for raw_row in rows:
        out: dict[str, Any] = {"type": match.entity_type}
        extra: dict[str, Any] = {}

        for raw_col, val in raw_row.items():
            if val is None:
                continue
            val_str = str(val).strip()
            if not val_str:
                continue

            mapped_field = match.column_map.get(raw_col)
            if mapped_field:
                out[mapped_field] = val
            else:
                extra[raw_col] = val

        if extra:
            out["extra_fields"] = extra

        # --- Address hygiene (same as mapper.apply_column_map) ---
        prop_val = str(out.get("property_address") or "").strip()
        if prop_val:
            normalized = normalize_address(prop_val)
            if is_section_header(out):
                current_property = normalized
                continue
            if is_junk_property(normalized):
                continue
            out["property_address"] = normalized
            current_property = normalized
        elif current_property:
            if is_junk_property(current_property):
                continue
            out["property_address"] = current_property

        has_meaningful_data = any(
            k not in ("type", "extra_fields") and v is not None for k, v in out.items()
        )
        if has_meaningful_data:
            mapped.append(out)

    return mapped
