"""Operations — leases, maintenance, tenants, actions, notes.

Day-to-day property operations: lease lifecycle, maintenance tracking,
tenant management, action items, and review notes.
"""

from remi.application.api.operations.actions import router as actions_router
from remi.application.api.operations.leases import router as leases_router
from remi.application.api.operations.maintenance import router as maintenance_router
from remi.application.api.operations.notes import router as notes_router
from remi.application.api.operations.tenants import router as tenants_router

__all__ = [
    "actions_router",
    "leases_router",
    "maintenance_router",
    "notes_router",
    "tenants_router",
]
