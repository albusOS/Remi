"""Canonical entity ID functions — the single source of truth for natural keys.

Every entity type has one function that encodes its natural key contract.
Both API routes and the ingestion pipeline call these functions, ensuring
the same real-world thing always gets the same ID regardless of entry path.

Layer 2 adds content_hash() for row-level change detection.
"""

from __future__ import annotations

import hashlib
import json

from remi.types.text import slugify

__all__ = [
    "balance_observation_id",
    "content_hash",
    "lease_id",
    "maintenance_id",
    "manager_id",
    "note_id",
    "owner_id",
    "property_id",
    "tenant_id",
    "unit_id",
    "vendor_id",
]


def property_id(name: str) -> str:
    return slugify(f"property:{name}")


def unit_id(property_id: str, unit_number: str) -> str:
    return slugify(f"unit:{property_id}:{unit_number}")


def tenant_id(name: str, property_id: str) -> str:
    return slugify(f"tenant:{name}:{property_id}")


def lease_id(tenant_name: str, property_id: str, unit_number: str) -> str:
    return slugify(f"lease:{tenant_name}:{property_id}:{unit_number}")


def maintenance_id(property_id: str, unit_number: str, title: str) -> str:
    return slugify(f"maint:{property_id}:{unit_number}:{title or 'request'}")


def manager_id(name: str) -> str:
    return slugify(f"manager:{name}")


def owner_id(name: str) -> str:
    return slugify(f"owner:{name}")


def vendor_id(name: str) -> str:
    return slugify(f"vendor:{name}")


def note_id(entity_id: str, doc_id: str, index: int) -> str:
    return slugify(f"note:{entity_id}:{doc_id}:{index}")


def balance_observation_id(tenant_id: str, doc_id: str) -> str:
    """Stable ID per tenant × document — ensures idempotent re-ingestion."""
    return slugify(f"bal_obs:{tenant_id}:{doc_id}")


def content_hash(data: dict[str, object], exclude: set[str] | None = None) -> str:
    """SHA-256 of sorted, JSON-serialized field values.

    Used for row-level change detection: if the hash matches what's already
    stored, the upsert can short-circuit to NOOP.
    """
    skip = {"id", "created_at", "source_document_id", "content_hash"} | (exclude or set())
    canonical = {k: v for k, v in sorted(data.items()) if k not in skip and v is not None}
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, default=str).encode()).hexdigest()
