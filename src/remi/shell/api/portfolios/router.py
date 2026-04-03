"""REST endpoints for portfolios."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from remi.types.errors import NotFoundError
from remi.shell.api.portfolios.schemas import (
    PortfolioDetail,
    PortfolioListResponse,
)
from remi.domain.intelligence.queries.portfolios import PortfolioSummaryResult
from remi.domain.core.portfolio.protocols import PortfolioRepository
from remi.domain.intelligence.queries.portfolios import PortfolioQueryService
from remi.shell.api.dependencies import get_portfolio_query, get_property_store

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


@router.get("", response_model=PortfolioListResponse)
async def list_portfolios(
    manager_id: str | None = None,
    svc: PortfolioQueryService = Depends(get_portfolio_query),
) -> PortfolioListResponse:
    items = await svc.list_portfolios(manager_id=manager_id)
    return PortfolioListResponse(portfolios=items)


@router.get("/{portfolio_id}", response_model=PortfolioDetail)
async def get_portfolio(
    portfolio_id: str,
    ps: PortfolioRepository = Depends(get_property_store),
) -> PortfolioDetail:
    portfolio = await ps.get_portfolio(portfolio_id)
    if not portfolio:
        raise NotFoundError("Portfolio", portfolio_id)
    return PortfolioDetail(
        id=portfolio.id,
        manager_id=portfolio.manager_id,
        name=portfolio.name,
        description=portfolio.description,
        property_ids=portfolio.property_ids,
        created_at=portfolio.created_at.isoformat(),
    )


@router.get("/{portfolio_id}/summary", response_model=PortfolioSummaryResult)
async def portfolio_summary(
    portfolio_id: str,
    svc: PortfolioQueryService = Depends(get_portfolio_query),
) -> PortfolioSummaryResult:
    result = await svc.portfolio_summary(portfolio_id)
    if not result:
        raise NotFoundError("Portfolio", portfolio_id)
    return result
