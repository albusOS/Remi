"""Operations — leases, maintenance, tenants, actions, notes.

Queries:
    LeaseResolver          Lease list, expiring leases, tenant detail
    MaintenanceResolver    Maintenance list and summary

API:
    leases_router          /leases CRUD
    maintenance_router     /maintenance CRUD
    tenants_router         /tenants CRUD
    actions_router         /actions CRUD
    notes_router           /notes CRUD
"""

from pathlib import Path

from .api import actions_router, leases_router, maintenance_router, notes_router, tenants_router
from .queries import LeaseResolver, MaintenanceResolver

MANIFEST_PATH = Path(__file__).parent / "app.yaml"

__all__ = [
    "LeaseResolver",
    "MANIFEST_PATH",
    "MaintenanceResolver",
    "actions_router",
    "leases_router",
    "maintenance_router",
    "notes_router",
    "tenants_router",
]
