"""FastAPI dependency injection for application routes.

Provides ``Ctr`` — a typed DI alias used by all ``application/*.api``
route handlers to access the container.

``ContainerProtocol`` declares the attributes that application-layer
routes actually use.  Resolver types are imported directly from their
defining modules (not through barrel ``__init__.py`` files) to avoid
the barrel→api→dependencies cycle.

Infrastructure types from ``agent/`` and ``application/core/`` are
imported normally — they sit in inner rings with no slice dependencies.
"""

from __future__ import annotations

from typing import Annotated, Protocol

from fastapi import Depends, Request

from remi.agent.documents import ContentStore
from remi.agent.events import EventBuffer, EventBus
from remi.agent.graph import WorldModel
from remi.agent.signals import DomainSchema
from remi.agent.tasks import TaskSupervisor
from remi.application.core import EventStore, PropertyStore
from remi.application.core.protocols import DocumentIngester
from remi.application.intelligence.search import SearchService
from remi.application.intelligence.trends import TrendResolver
from remi.application.operations.delinquency import DelinquencyResolver
from remi.application.operations.leases import LeaseResolver
from remi.application.operations.maintenance import MaintenanceResolver
from remi.application.operations.vacancies import VacancyResolver
from remi.application.portfolio.auto_assign import AutoAssignService
from remi.application.portfolio.dashboard import DashboardBuilder
from remi.application.portfolio.managers import ManagerResolver
from remi.application.portfolio.properties import PropertyResolver
from remi.application.portfolio.rent_roll import RentRollResolver


class ContainerProtocol(Protocol):
    """Structural interface for the DI container as seen by application routes.

    All attributes are fully typed. Infrastructure types live in inner rings.
    Resolver types are imported from their defining modules (bypassing the
    barrel ``__init__.py`` which also exports API routers that depend on
    this module).
    """

    # -- Infrastructure (inner-ring types) ------------------------------------
    property_store: PropertyStore
    content_store: ContentStore
    event_bus: EventBus
    event_buffer: EventBuffer
    event_store: EventStore
    world_model: WorldModel
    domain_schema: DomainSchema

    # -- Portfolio resolvers --------------------------------------------------
    manager_resolver: ManagerResolver
    property_resolver: PropertyResolver
    rent_roll_resolver: RentRollResolver
    dashboard_builder: DashboardBuilder
    auto_assign_service: AutoAssignService

    # -- Operations resolvers -------------------------------------------------
    lease_resolver: LeaseResolver
    maintenance_resolver: MaintenanceResolver
    delinquency_resolver: DelinquencyResolver
    vacancy_resolver: VacancyResolver

    # -- Intelligence resolvers -----------------------------------------------
    search_service: SearchService
    trend_resolver: TrendResolver

    # -- Services -------------------------------------------------------------
    document_ingest: DocumentIngester
    task_supervisor: TaskSupervisor


def get_container(request: Request) -> ContainerProtocol:
    """Pull the DI container off ``request.app.state``.

    Override this via ``app.dependency_overrides`` in tests.
    """
    return request.app.state.container  # type: ignore[return-value]


Ctr = Annotated[ContainerProtocol, Depends(get_container)]
