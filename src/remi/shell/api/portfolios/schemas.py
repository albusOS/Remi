"""API schemas for portfolios.

Read-model types are owned by the service layer and re-exported here.
Only request types, detail views for raw entity access, and envelope
wrappers are defined in this module.
"""

from __future__ import annotations

from pydantic import BaseModel

from remi.domain.intelligence.queries.portfolios import (
    PortfolioListItem,
    PortfolioSummaryResult,
    PropertyInPortfolio,
)

__all__ = [
    "PortfolioDetail",
    "PortfolioListItem",
    "PortfolioListResponse",
    "PortfolioSummaryResult",
    "PropertyInPortfolio",
]


class PortfolioListResponse(BaseModel):
    portfolios: list[PortfolioListItem]


class PortfolioDetail(BaseModel):
    """Thin projection of the raw Portfolio entity for GET /portfolios/{id}."""

    id: str
    manager_id: str
    name: str
    description: str
    property_ids: list[str]
    created_at: str
