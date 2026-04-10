"""Kernel — the Agent OS boot object.

Owns every infrastructure subsystem. Products call ``Kernel.boot(settings)``,
register their tool providers, load manifests, and run.

    kernel = Kernel.boot(settings)
    MyToolProvider(my_db).register(kernel.tool_registry)
    kernel.load_manifests("./agents/")
    await kernel.serve(port=8000)

The kernel never imports from ``application/`` or ``shell/``. It calls
only ``agent/`` factories that already exist.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog
from pydantic import BaseModel, Field

from remi.agent.context import build_context_builder
from remi.agent.events import (
    DomainEvent,
    EventBuffer,
    EventBus,
    InMemoryEventBuffer,
    build_event_bus,
)
from remi.agent.events.factory import EventBusSettings
from remi.agent.llm import LLMProviderFactory, build_provider_factory
from remi.agent.llm.types import LLMSettings, SecretsSettings
from remi.agent.memory import MemoryStore, build_memory_store
from remi.agent.memory.factory import MemoryStoreSettings
from remi.agent.memory.recall import MemoryRecallService
from remi.agent.observe import LLMUsageLedger, Tracer, build_trace_store
from remi.agent.observe.factory import TraceStoreSettings
from remi.agent.observe.types import TraceStore
from remi.agent.runtime import RetryPolicy
from remi.agent.runtime.runner import AgentRuntime
from remi.agent.sandbox import Sandbox, build_sandbox
from remi.agent.sandbox.types import SandboxSettings
from remi.agent.sessions import build_chat_session_store
from remi.agent.sessions.factory import SessionStoreSettings
from remi.agent.signals import DomainSchema
from remi.agent.tasks import TaskSupervisor, build_task_pool
from remi.agent.tasks.factory import TaskQueueSettings
from remi.agent.tasks.pool import TaskPool
from remi.agent.tools import (
    AnalysisToolProvider,
    DelegationToolProvider,
    HumanToolProvider,
    InMemoryToolCatalog,
    MemoryToolProvider,
)
from remi.agent.types import ChatSessionStore, ToolRegistry
from remi.agent.vectors import Embedder, VectorStore, build_embedder, build_vector_store
from remi.agent.vectors.types import EmbeddingsSettings, VectorStoreSettings
from remi.agent.workflow import WorkflowRunner
from remi.agent.workflow.registry import ManifestRegistry, discover_manifests
from remi.agent.workforce import Workforce

logger = structlog.get_logger(__name__)


class KernelSettings(BaseModel):
    """Aggregate settings for the Agent OS kernel.

    Assembles subsystem settings. Products wrap or extend this with
    their own product-level settings (API bind, domain stores, etc.).
    """

    secrets: SecretsSettings = Field(default_factory=SecretsSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    sandbox: SandboxSettings = Field(default_factory=SandboxSettings)
    embeddings: EmbeddingsSettings = Field(default_factory=EmbeddingsSettings)
    vectors: VectorStoreSettings = Field(default_factory=VectorStoreSettings)
    memory: MemoryStoreSettings = Field(default_factory=MemoryStoreSettings)
    tracing: TraceStoreSettings = Field(default_factory=TraceStoreSettings)
    sessions: SessionStoreSettings = Field(default_factory=SessionStoreSettings)
    event_bus: EventBusSettings = Field(default_factory=EventBusSettings)
    task_queue: TaskQueueSettings = Field(default_factory=TaskQueueSettings)
    dsn: str = ""
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    api_url: str = ""


class Kernel:
    """The Agent OS kernel — owns all infrastructure subsystems.

    Use ``Kernel.boot(settings)`` to create. Never construct directly.
    """

    def __init__(
        self,
        *,
        event_bus: EventBus,
        event_buffer: EventBuffer,
        memory_store: MemoryStore,
        recall_service: MemoryRecallService,
        tool_registry: ToolRegistry,
        provider_factory: LLMProviderFactory,
        session_store: ChatSessionStore,
        trace_store: TraceStore,
        usage_ledger: LLMUsageLedger,
        tracer: Tracer,
        sandbox: Sandbox,
        vector_store: VectorStore,
        embedder: Embedder,
        runtime: AgentRuntime,
        workflow_runner: WorkflowRunner,
        task_pool: TaskPool,
        workforce: Workforce,
        supervisor: TaskSupervisor,
        manifest_registry: ManifestRegistry,
        settings: KernelSettings,
    ) -> None:
        self.event_bus = event_bus
        self.event_buffer = event_buffer
        self.memory_store = memory_store
        self.recall_service = recall_service
        self.tool_registry = tool_registry
        self.provider_factory = provider_factory
        self.session_store = session_store
        self.trace_store = trace_store
        self.usage_ledger = usage_ledger
        self.tracer = tracer
        self.sandbox = sandbox
        self.vector_store = vector_store
        self.embedder = embedder
        self.runtime = runtime
        self.workflow_runner = workflow_runner
        self.task_pool = task_pool
        self.workforce = workforce
        self.supervisor = supervisor
        self.manifest_registry = manifest_registry
        self.settings = settings

    @classmethod
    def boot(
        cls,
        settings: KernelSettings | dict[str, Any] | None = None,
        *,
        domain_schema: DomainSchema | None = None,
        manifest_dirs: list[str | Path] | None = None,
        registry: ManifestRegistry | None = None,
    ) -> Kernel:
        """Boot the Agent OS kernel from settings.

        Calls every ``agent/`` factory in the right order and wires
        the complete infrastructure graph. Returns a ready-to-use
        kernel. Products layer their own tools and stores on top.

        ``domain_schema`` is optional — defaults to an empty schema
        for products that don't use a knowledge graph.

        ``manifest_dirs`` is a list of directories to scan for
        ``app.yaml`` manifests. If omitted, only explicitly registered
        manifests are available.

        ``registry`` is an optional pre-populated ``ManifestRegistry``.
        Products that register manifests before boot (e.g. via
        ``capabilities.py``) pass their registry here so that the
        kernel's workforce and agent loading use the same registry.
        """
        if settings is None:
            settings = KernelSettings()
        elif isinstance(settings, dict):
            settings = KernelSettings.model_validate(settings)

        dsn = settings.dsn or settings.secrets.database_url
        api_url = settings.api_url

        # -- Event bus + buffer ------------------------------------------------
        event_bus: EventBus = build_event_bus(settings.event_bus)
        event_buffer: EventBuffer = InMemoryEventBuffer(capacity=8192)

        async def _buffer_sink(event: DomainEvent) -> None:
            await event_buffer.append(event)

        event_bus.subscribe("*", _buffer_sink)

        # -- Memory ------------------------------------------------------------
        memory_store: MemoryStore = build_memory_store(settings.memory, dsn=dsn)
        recall_service = MemoryRecallService(memory_store)

        # -- Tool registry -----------------------------------------------------
        tool_registry: ToolRegistry = InMemoryToolCatalog()

        # -- LLM providers -----------------------------------------------------
        provider_factory: LLMProviderFactory = build_provider_factory(settings.secrets)

        # -- Sessions ----------------------------------------------------------
        session_store: ChatSessionStore = build_chat_session_store(settings.sessions)

        # -- Tracing -----------------------------------------------------------
        trace_store = build_trace_store(settings.tracing)
        usage_ledger = LLMUsageLedger()
        tracer = Tracer(trace_store)

        # -- Sandbox -----------------------------------------------------------
        sandbox: Sandbox = build_sandbox(settings.sandbox, api_url=api_url)

        # -- Vectors -----------------------------------------------------------
        vector_store: VectorStore = build_vector_store(settings.vectors, dsn=dsn)
        embedder: Embedder = build_embedder(settings.embeddings, settings.secrets)

        # -- Workflow runner ---------------------------------------------------
        workflow_runner = WorkflowRunner(
            provider_factory=provider_factory,
            default_provider=settings.llm.default_provider,
            default_model=settings.llm.default_model,
            usage_ledger=usage_ledger,
            tool_registry=tool_registry,
        )

        # -- Kernel tool providers (generic, not product-specific) -------------
        AnalysisToolProvider(sandbox).register(tool_registry)
        MemoryToolProvider(memory_store).register(tool_registry)

        # -- Context builder (optional domain schema) --------------------------
        schema = domain_schema or DomainSchema()
        context_builder = build_context_builder(
            domain=schema,
            world_model=None,
            vector_store=vector_store,
            embedder=embedder,
        )

        # -- Agent runtime -----------------------------------------------------
        runtime = AgentRuntime(
            provider_factory=provider_factory,
            tool_registry=tool_registry,
            sandbox=sandbox,
            memory_store=memory_store,
            tracer=tracer,
            chat_session_store=session_store,
            retry_policy=RetryPolicy(
                max_retries=settings.max_retries,
                delay_seconds=settings.retry_delay_seconds,
            ),
            default_provider=settings.llm.default_provider,
            default_model=settings.llm.default_model,
            domain_tbox=schema,
            context_builder=context_builder,
            usage_ledger=usage_ledger,
            recall_service=recall_service,
        )

        # -- Wire workflow ↔ runtime -------------------------------------------
        workflow_runner.set_agent_executor(runtime)

        # -- Manifest discovery ------------------------------------------------
        if registry is None:
            registry = ManifestRegistry()
        if manifest_dirs:
            for d in manifest_dirs:
                n = discover_manifests(d, registry=registry)
                logger.info("manifests_discovered", directory=str(d), count=n)

        # -- Workforce (topology from manifests) -------------------------------
        workforce = Workforce.from_manifests(registry.all_manifests())

        # -- Task pool + supervisor --------------------------------------------
        task_pool = build_task_pool(settings.task_queue)
        supervisor = TaskSupervisor(
            executor=runtime,
            event_bus=event_bus,
            pool=task_pool,
            workforce=workforce,
            workflow_executor=workflow_runner,
        )

        # -- Delegation + human tools (need supervisor + workforce) ------------
        DelegationToolProvider(supervisor, workforce=workforce).register(tool_registry)
        HumanToolProvider(supervisor).register(tool_registry)

        logger.info(
            "kernel_booted",
            llm_provider=settings.llm.default_provider,
            llm_model=settings.llm.default_model,
            sandbox_backend=settings.sandbox.backend,
            event_bus_backend=settings.event_bus.backend,
            task_queue_backend=settings.task_queue.backend,
            manifests=len(registry),
            agents=len(workforce.agents),
        )

        return cls(
            event_bus=event_bus,
            event_buffer=event_buffer,
            memory_store=memory_store,
            recall_service=recall_service,
            tool_registry=tool_registry,
            provider_factory=provider_factory,
            session_store=session_store,
            trace_store=trace_store,
            usage_ledger=usage_ledger,
            tracer=tracer,
            sandbox=sandbox,
            vector_store=vector_store,
            embedder=embedder,
            runtime=runtime,
            workflow_runner=workflow_runner,
            task_pool=task_pool,
            workforce=workforce,
            supervisor=supervisor,
            manifest_registry=registry,
            settings=settings,
        )

    def load_manifests(self, *directories: str | Path) -> int:
        """Discover and register manifests from directories.

        Returns the total number of new manifests discovered.
        Can be called after boot to add more agents/workflows.
        """
        total = 0
        for d in directories:
            n = discover_manifests(d, registry=self.manifest_registry)
            total += n
        if total > 0:
            self.workforce = Workforce.from_manifests(
                list(self.manifest_registry.all_manifests()),
            )
            self.supervisor.update_workforce(self.workforce)
        return total
