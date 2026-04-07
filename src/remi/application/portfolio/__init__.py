"""Portfolio — managers, properties, units, owners, rent-roll.

Queries:
    ManagerResolver        Director-level portfolio roll-up
    PropertyResolver       Property list, detail, cross-property units
    RentRollResolver       Detailed rent-roll assembly per property
    property_ids_for_manager / property_ids_for_owner   Scope helpers

Mutations:
    AutoAssignService      KB-tag-based property-to-manager assignment

API:
    managers_router        /managers CRUD + meeting briefs
    properties_router      /properties CRUD + rent-roll
    units_router           /units CRUD
    owners_router          /owners listing
"""

from pathlib import Path

from .api import managers_router, owners_router, properties_router, units_router
from .mutations import AutoAssignService
from .queries import (
    ManagerResolver,
    PropertyResolver,
    RentRollResolver,
    property_ids_for_manager,
    property_ids_for_owner,
)

MANIFEST_PATH = Path(__file__).parent / "app.yaml"

__all__ = [
    "AutoAssignService",
    "MANIFEST_PATH",
    "ManagerResolver",
    "PropertyResolver",
    "RentRollResolver",
    "managers_router",
    "owners_router",
    "properties_router",
    "property_ids_for_manager",
    "property_ids_for_owner",
    "units_router",
]
