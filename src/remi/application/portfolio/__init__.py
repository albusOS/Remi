"""Portfolio — managers, properties, units, owners, rent-roll, dashboard.

Resolvers:
    ManagerResolver        Director-level portfolio roll-up per manager
    PropertyResolver       Property list, detail, cross-property units
    RentRollResolver       Detailed rent-roll assembly per property
    DashboardBuilder       Portfolio-wide dashboard overview

Mutations:
    AutoAssignService      KB-tag-based property-to-manager assignment

Scope helpers:
    property_ids_for_manager / property_ids_for_owner

API routers are imported directly by the shell via ``capabilities.py``
string references — they are NOT re-exported here to avoid barrel→api
→dependencies circular imports.
"""

from remi.application.portfolio.auto_assign import AutoAssignService
from remi.application.portfolio.dashboard import DashboardBuilder
from remi.application.portfolio.managers import ManagerResolver
from remi.application.portfolio.properties import (
    PropertyResolver,
    property_ids_for_manager,
    property_ids_for_owner,
)
from remi.application.portfolio.rent_roll import RentRollResolver

__all__ = [
    "AutoAssignService",
    "DashboardBuilder",
    "ManagerResolver",
    "PropertyResolver",
    "RentRollResolver",
    "property_ids_for_manager",
    "property_ids_for_owner",
]
