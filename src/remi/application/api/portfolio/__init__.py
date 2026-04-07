"""Portfolio management — managers, properties, units, owners.

The director's view of her book of business: who manages what,
where the assets are, and how the units are configured.
"""

from remi.application.api.portfolio.managers import router as managers_router
from remi.application.api.portfolio.owners import router as owners_router
from remi.application.api.portfolio.properties import router as properties_router
from remi.application.api.portfolio.units import router as units_router

__all__ = [
    "managers_router",
    "owners_router",
    "properties_router",
    "units_router",
]
