"""REMI dependency injection container — pure wiring only.

Calls factory functions from the modules that own the things being built.
No backend selection logic, no LLM adapter registration, no closures.

Only attributes read outside this module are stored as ``self.*``.
Internal intermediaries are local variables.
"""

from __future__ import annotations

from typing import Any

from remi.agent.runtime.retry import RetryPolicy
from remi.agent.runtime.runner import ChatAgentService
from remi.tools import register_all_tools
from remi.tools.delegation import AgentInvoker, register_delegation_tools
from remi.tools.registry import InMemoryToolRegistry
from remi.tools.snapshots import register_snapshot_tools
from remi.tools.workflows import SubAgentInvoker, register_workflow_tools
from remi.agent.types import ChatSessionStore
from remi.documents.types import DocumentStore
from remi.graph.stores import KnowledgeStore
from remi.signals import DomainRulebook, FeedbackStore, MutableRulebook, SignalStore
from remi.agent.types import ToolRegistry
from remi.observe.types import Tracer, TraceStore
from remi.vectors.types import Embedder, VectorStore
from remi.evaluators.pipeline import build_signal_pipeline
from remi.agent.context.builder import build_context_builder
from remi.ingestion.service import IngestionService
from remi.ingestion.llm_adapters import make_classify_fn, make_enrich_fn
from remi.ingestion.pipeline import DocumentIngestService
from remi.ingestion.seed import SeedService
from remi.graph.bridge import BridgedKnowledgeGraph
from remi.ontology.bridge import build_knowledge_graph
from remi.ontology.schema import load_domain_yaml, seed_knowledge_graph
from remi.search.pattern import PatternDetector
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
from remi.llm.factory import LLMProviderFactory, build_provider_factory
from remi.sandbox.factory import build_sandbox
from remi.sandbox.types import Sandbox
from remi.agent.mem import InMemoryChatSessionStore
from remi.stores.factory import build_document_store, build_property_store, build_rollup_store
from remi.graph.mem import InMemoryKnowledgeStore, InMemoryMemoryStore
from remi.signals.mem import (
    InMemoryFeedbackStore,
    InMemoryHypothesisStore,
    InMemorySignalStore,
)
from remi.observe.mem import InMemoryTraceStore
from remi.vectors.embedder import build_embedder
from remi.ingestion.embedding import EmbeddingPipeline
from remi.vectors.store import InMemoryVectorStore
from remi.shell.config.settings import RemiSettings


class Container:
    """REMI container — wires all services for the real estate product."""

    def __init__(self, settings: RemiSettings | None = None) -> None:
        self.settings = settings or RemiSettings()

        # -- Core infrastructure -----------------------------------------------
        memory_store = InMemoryMemoryStore()
        self.knowledge_store: KnowledgeStore = InMemoryKnowledgeStore()
        self.tool_registry: ToolRegistry = InMemoryToolRegistry()
        self.provider_factory: LLMProviderFactory = build_provider_factory(
            self.settings.secrets,
        )

        # -- Stores ------------------------------------------------------------
        self.chat_session_store: ChatSessionStore = InMemoryChatSessionStore()
        self.property_store: PropertyStore
        self._db_engine: Any
        self._db_session_factory: Any
        self.property_store, self._db_engine, self._db_session_factory = build_property_store(
            self.settings
        )
        self.document_store: DocumentStore = build_document_store(self._db_session_factory)
        rollup_store = build_rollup_store(self._db_session_factory)

        # -- Knowledge graph ---------------------------------------------------
        self.knowledge_graph: BridgedKnowledgeGraph = build_knowledge_graph(
            self.property_store,
            self.knowledge_store,
        )
        self._bootstrap_pending = True

        # -- Trace layer -------------------------------------------------------
        self.trace_store: TraceStore = InMemoryTraceStore()
        tracer = Tracer(self.trace_store)

        # -- Signal layer ------------------------------------------------------
        raw_domain = load_domain_yaml()
        self.domain_rulebook: DomainRulebook = DomainRulebook.from_yaml(raw_domain)
        mutable_rulebook = MutableRulebook(self.domain_rulebook)
        self.signal_store: SignalStore = InMemorySignalStore()
        self.feedback_store: FeedbackStore = InMemoryFeedbackStore()

        # -- Hypothesis (internal) ---------------------------------------------
        hypothesis_store = InMemoryHypothesisStore()
        pattern_detector = PatternDetector(
            knowledge_graph=self.knowledge_graph,
            hypothesis_store=hypothesis_store,
        )

        # -- Sandbox -----------------------------------------------------------
        self.sandbox: Sandbox = build_sandbox(self.settings)

        # -- Vectors -----------------------------------------------------------
        self.vector_store: VectorStore = InMemoryVectorStore()
        self.embedder: Embedder = build_embedder(
            self.settings.embeddings,
            self.settings.secrets,
        )

        # -- Services ----------------------------------------------------------
        ingestion_service = IngestionService(
            knowledge_store=self.knowledge_store,
            property_store=self.property_store,
            classify_fn=make_classify_fn(lambda: self.chat_agent, self.settings.secrets),
        )
        self.dashboard_service = DashboardQueryService(
            property_store=self.property_store,
            knowledge_store=self.knowledge_store,
        )
        self.snapshot_service = SnapshotService(
            property_store=self.property_store,
            rollup_store=rollup_store,
        )
        self.property_query = PropertyQueryService(property_store=self.property_store)
        self.portfolio_query = PortfolioQueryService(property_store=self.property_store)
        self.lease_query = LeaseQueryService(property_store=self.property_store)
        self.maintenance_query = MaintenanceQueryService(property_store=self.property_store)
        self.manager_review = ManagerReviewService(property_store=self.property_store)
        self.rent_roll_service = RentRollService(property_store=self.property_store)
        self.auto_assign_service = AutoAssignService(
            property_store=self.property_store,
            knowledge_store=self.knowledge_store,
            snapshot_service=self.snapshot_service,
        )

        # -- Signal pipeline ---------------------------------------------------
        self.signal_pipeline = build_signal_pipeline(
            domain=mutable_rulebook,
            property_store=self.property_store,
            signal_store=self.signal_store,
            snapshot_service=self.snapshot_service,
            knowledge_graph=self.knowledge_graph,
            tracer=tracer,
        )

        # -- Embedding pipeline ------------------------------------------------
        self.embedding_pipeline = EmbeddingPipeline(
            property_store=self.property_store,
            vector_store=self.vector_store,
            embedder=self.embedder,
            document_store=self.document_store,
            signal_store=self.signal_store,
        )

        # -- Search service ----------------------------------------------------
        self.search_service = SearchService(self.vector_store, self.embedder)

        # -- Tools (phase 1 — before chat_agent exists) ------------------------
        _api_base = f"http://127.0.0.1:{self.settings.api.port}"
        register_all_tools(
            self.tool_registry,
            knowledge_graph=self.knowledge_graph,
            document_store=self.document_store,
            property_store=self.property_store,
            memory_store=memory_store,
            signal_store=self.signal_store,
            vector_store=self.vector_store,
            embedder=self.embedder,
            trace_store=self.trace_store,
            sandbox=self.sandbox,
            search_service=self.search_service,
            api_base_url=_api_base,
        )

        # -- Document ingestion ------------------------------------------------
        self.document_ingest = DocumentIngestService(
            document_store=self.document_store,
            ingestion_service=ingestion_service,
            knowledge_store=self.knowledge_store,
            property_store=self.property_store,
            snapshot_service=self.snapshot_service,
            signal_pipeline=self.signal_pipeline,
            pattern_detector=pattern_detector,
            embedding_pipeline=self.embedding_pipeline,
            enrich_fn=make_enrich_fn(lambda: self.chat_agent, self.settings.secrets),
        )

        # -- Seed service ------------------------------------------------------
        self.seed_service = SeedService(
            document_ingest=self.document_ingest,
            auto_assign=self.auto_assign_service,
            signal_pipeline=self.signal_pipeline,
            embedding_pipeline=self.embedding_pipeline,
            property_store=self.property_store,
            snapshot_service=self.snapshot_service,
            rollup_store=rollup_store,
        )

        # -- Chat agent --------------------------------------------------------
        context_builder = build_context_builder(
            domain=mutable_rulebook,
            signal_store=self.signal_store,
            knowledge_graph=self.knowledge_graph,
            vector_store=self.vector_store,
            embedder=self.embedder,
        )
        self.chat_agent = ChatAgentService(
            provider_factory=self.provider_factory,
            tool_registry=self.tool_registry,
            sandbox=self.sandbox,
            domain_rulebook=self.domain_rulebook,
            signal_store=self.signal_store,
            memory_store=memory_store,
            tracer=tracer,
            chat_session_store=self.chat_session_store,
            retry_policy=RetryPolicy(
                max_retries=self.settings.execution.max_retries,
                delay_seconds=self.settings.execution.retry_delay_seconds,
            ),
            default_provider=self.settings.llm.default_provider,
            default_model=self.settings.llm.default_model,
            context_builder=context_builder,
        )

        # -- Tools (phase 2 — after chat_agent exists) -------------------------
        register_snapshot_tools(
            self.tool_registry,
            snapshot_service=self.snapshot_service,
        )
        from typing import cast

        register_workflow_tools(
            self.tool_registry,
            property_store=self.property_store,
            knowledge_graph=self.knowledge_graph,
            manager_review=self.manager_review,
            dashboard_service=self.dashboard_service,
            sub_agent=cast(SubAgentInvoker, self.chat_agent),
        )
        register_delegation_tools(
            self.tool_registry,
            agent_invoker=cast(AgentInvoker, self.chat_agent),
        )

    async def ensure_bootstrapped(self) -> None:
        if self._bootstrap_pending:
            if self._db_engine is not None:
                from remi.db.engine import create_tables

                await create_tables(self._db_engine)
            await seed_knowledge_graph(self.knowledge_graph)
            self._bootstrap_pending = False
