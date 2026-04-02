"""FastAPI dependency injection — narrow typed accessors for route handlers.

Each accessor extracts exactly one service or port from the container,
enforcing the triangle: Container (broad) → dependencies.py (mediates) →
routers (each endpoint declares only what it needs).

All accessor functions chain through ``get_container`` so that
``app.dependency_overrides[get_container]`` is sufficient to redirect
every downstream dependency (critical for test fixtures).
"""

from __future__ import annotations

from fastapi import Depends, Request

from remi.agent.runtime.runner import ChatAgentService
from remi.agent.types import ChatSessionStore
from remi.documents.types import DocumentStore
from remi.graph.stores import KnowledgeStore
from remi.signals import FeedbackStore, SignalStore
from remi.signals.composite import CompositeProducer
from remi.ingestion.pipeline import DocumentIngestService
from remi.ingestion.seed import SeedService
from remi.graph.bridge import BridgedKnowledgeGraph
from remi.search.service import SearchService
from remi.portfolio.protocols import PropertyStore
from remi.queries.auto_assign import AutoAssignService
from remi.queries.dashboard import DashboardQueryService
from remi.queries.leases import LeaseQueryService
from remi.queries.maintenance import MaintenanceQueryService
from remi.queries.managers import ManagerReviewService
from remi.queries.portfolios import PortfolioQueryService
from remi.queries.properties import PropertyQueryService
from remi.queries.rent_roll import RentRollService
from remi.queries.snapshots import SnapshotService
from remi.llm.factory import LLMProviderFactory
from remi.shell.config.container import Container
from remi.shell.config.settings import RemiSettings


def get_container(request: Request) -> Container:
    return request.app.state.container  # type: ignore[no-any-return]


def get_property_store(c: Container = Depends(get_container)) -> PropertyStore:
    return c.property_store


def get_signal_store(c: Container = Depends(get_container)) -> SignalStore:
    return c.signal_store


def get_feedback_store(c: Container = Depends(get_container)) -> FeedbackStore:
    return c.feedback_store


def get_signal_pipeline(c: Container = Depends(get_container)) -> CompositeProducer:
    return c.signal_pipeline


def get_knowledge_graph(c: Container = Depends(get_container)) -> BridgedKnowledgeGraph:
    return c.knowledge_graph


def get_document_store(c: Container = Depends(get_container)) -> DocumentStore:
    return c.document_store


def get_document_ingest(c: Container = Depends(get_container)) -> DocumentIngestService:
    return c.document_ingest


def get_chat_agent(c: Container = Depends(get_container)) -> ChatAgentService:
    return c.chat_agent


def get_chat_session_store(c: Container = Depends(get_container)) -> ChatSessionStore:
    return c.chat_session_store


def get_dashboard_service(c: Container = Depends(get_container)) -> DashboardQueryService:
    return c.dashboard_service


def get_snapshot_service(c: Container = Depends(get_container)) -> SnapshotService:
    return c.snapshot_service


def get_knowledge_store(c: Container = Depends(get_container)) -> KnowledgeStore:
    return c.knowledge_store


def get_settings(c: Container = Depends(get_container)) -> RemiSettings:
    return c.settings


def get_provider_factory(c: Container = Depends(get_container)) -> LLMProviderFactory:
    return c.provider_factory


def get_property_query(c: Container = Depends(get_container)) -> PropertyQueryService:
    return c.property_query


def get_portfolio_query(c: Container = Depends(get_container)) -> PortfolioQueryService:
    return c.portfolio_query


def get_lease_query(c: Container = Depends(get_container)) -> LeaseQueryService:
    return c.lease_query


def get_maintenance_query(c: Container = Depends(get_container)) -> MaintenanceQueryService:
    return c.maintenance_query


def get_manager_review(c: Container = Depends(get_container)) -> ManagerReviewService:
    return c.manager_review


def get_rent_roll_service(c: Container = Depends(get_container)) -> RentRollService:
    return c.rent_roll_service


def get_auto_assign_service(c: Container = Depends(get_container)) -> AutoAssignService:
    return c.auto_assign_service


def get_search_service(c: Container = Depends(get_container)) -> SearchService:
    return c.search_service


def get_seed_service(c: Container = Depends(get_container)) -> SeedService:
    return c.seed_service
