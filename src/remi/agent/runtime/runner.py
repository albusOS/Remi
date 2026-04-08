"""AgentRuntime — run named agents in single-shot or multi-turn chat.

Lean invocation facade. Loads agent configs from YAML manifests, builds
runtime contexts, and delegates execution to ``AgentNode``. Session
state management lives in ``AgentSessions`` — this module only invokes.

**Request routing**: Before entering the agent loop, ``ask()`` runs the
injected ``RequestRouter`` to classify the question into a tier:

- ``direct`` — single LLM call, no tools, no data fetch
- ``query``  — data fetched in-process via ``DataResolver``, formatted
  by a single LLM call, no agent loop
- ``agent``  — full think-act-observe loop with sandbox and tools
"""

from __future__ import annotations

import json
from typing import Any, Literal, Protocol

import structlog
import yaml

from remi.agent.context.builder import ContextBuilder
from remi.agent.llm.factory import LLMProviderFactory
from remi.agent.llm.types import Message
from remi.agent.memory import MemoryStore
from remi.agent.memory.recall import MemoryRecallService
from remi.agent.observe.types import Tracer
from remi.agent.observe.usage import LLMUsageLedger
from remi.agent.runtime.base import ModuleOutput
from remi.agent.runtime.config import RuntimeConfig
from remi.agent.runtime.deps import RunDeps, RunParams, RuntimeContext, ScopeContext
from remi.agent.runtime.node import AgentNode
from remi.agent.runtime.query_path import DataResolver, run_query_path
from remi.agent.runtime.retry import RetryPolicy
from remi.agent.runtime.router import RequestRouter, RoutingDecision, Tier
from remi.agent.runtime.sessions import AgentSessions
from remi.agent.sandbox.types import Sandbox
from remi.agent.signals import DomainTBox
from remi.agent.types import ChatSessionStore
from remi.agent.types import Message as ChatMessage
from remi.agent.types import ToolRegistry
from remi.agent.workflow.registry import get_manifest_path
from remi.types.errors import SessionNotFoundError
from remi.types.ids import new_run_id

logger = structlog.get_logger("remi.runner")


class EventCallback(Protocol):
    async def __call__(
        self,
        event_type: str,
        data: dict[str, Any],
    ) -> None: ...


class AgentRuntime:
    """Runs any named agent — stateless or session-aware.

    ``ask()`` is the single entry point.  The injected ``RequestRouter``
    classifies each question into a tier before execution begins.
    """

    def __init__(
        self,
        provider_factory: LLMProviderFactory,
        tool_registry: ToolRegistry,
        sandbox: Sandbox,
        domain_tbox: DomainTBox,
        memory_store: MemoryStore,
        tracer: Tracer,
        chat_session_store: ChatSessionStore,
        retry_policy: RetryPolicy,
        default_provider: str,
        default_model: str,
        context_builder: ContextBuilder | None = None,
        usage_ledger: LLMUsageLedger | None = None,
        recall_service: MemoryRecallService | None = None,
        router: RequestRouter | None = None,
        data_resolver: DataResolver | None = None,
        query_system_prompt: str = "",
    ) -> None:
        self._provider_factory = provider_factory
        self._tool_registry = tool_registry
        self._sandbox = sandbox
        self._domain_tbox = domain_tbox
        self._memory_store = memory_store
        self._tracer = tracer
        self._retry = retry_policy
        self._default_provider = default_provider
        self._default_model = default_model
        self._context_builder = context_builder
        self._usage_ledger = usage_ledger
        self._recall_service = recall_service
        self._router = router
        self._data_resolver = data_resolver
        self._query_system_prompt = query_system_prompt

        self.sessions = AgentSessions(chat_session_store)

    def get_runtime_config(self, agent_name: str) -> RuntimeConfig:
        """Return the ``RuntimeConfig`` for a registered agent manifest."""
        from remi.agent.workflow.loader import load_manifest_runtime

        return load_manifest_runtime(agent_name)

    # -- Public API --------------------------------------------------------

    async def ask(
        self,
        agent_name: str,
        question: str,
        *,
        session_id: str | None = None,
        on_event: EventCallback | None = None,
        manager_id: str | None = None,
    ) -> tuple[str | None, str]:
        """Run an agent. Returns ``(answer, run_id)``.

        The router classifies the question first.  For ``direct`` and
        ``query`` tiers, the agent loop is bypassed entirely.  For
        ``agent`` tier (or when no router is configured), the full
        think-act-observe loop runs.

        Session-aware calls always go through the agent loop (the
        session may have multi-turn context that the fast path can't
        handle).
        """
        if session_id is not None:
            return await self._ask_session(
                session_id, question, on_event=on_event,
            )

        decision = self._classify(question, manager_id=manager_id)
        log = logger.bind(agent=agent_name, tier=decision.tier.value)

        if decision.tier == Tier.DIRECT:
            return await self._ask_direct(question, on_event=on_event, log=log)

        if decision.tier == Tier.QUERY and self._data_resolver is not None:
            return await self._ask_query(
                question, decision, on_event=on_event, log=log,
            )

        return await self._ask_agent(
            agent_name, question, on_event=on_event,
        )

    async def run_chat_agent(
        self,
        agent_name: str,
        thread: list[Any],
        on_event: EventCallback | None = None,
        *,
        sandbox_session_id: str | None = None,
        mode: Literal["ask", "agent"] = "agent",
        provider: str | None = None,
        model: str | None = None,
        scope: ScopeContext | None = None,
        extra: dict[str, Any] | None = None,
    ) -> str:
        """Low-level: execute an agent over an explicit message thread."""
        config_dict, _runtime_cfg = self._load_agent_config(agent_name)
        config_dict["name"] = agent_name
        run_id = new_run_id()

        log = logger.bind(run_id=run_id, agent=agent_name, mode=mode)
        log.info("agent_run_start", thread_length=len(thread), provider=provider, model=model)

        sid = sandbox_session_id or f"chat-{run_id}"
        await self._ensure_sandbox_session(sid)

        params = RunParams(
            mode=mode,
            sandbox_session_id=sid,
            on_event=on_event,
            provider_name=provider,
            model_name=model,
        )
        ctx = self._build_context(run_id=run_id, params=params, scope=scope, extra=extra)

        thread_msgs: list[dict[str, Any]] = []
        for msg in thread:
            if isinstance(msg, ChatMessage):
                thread_msgs.append(msg.model_dump())
            elif isinstance(msg, dict):
                thread_msgs.append(msg)
            else:
                thread_msgs.append({"role": "user", "content": str(msg)})

        node = AgentNode(config=config_dict)
        output: ModuleOutput = await self._retry.execute(
            node.run,
            {"thread": thread_msgs},
            ctx,
        )

        answer = _extract_answer(output.value) or ""
        log.info(
            "agent_run_done",
            answer_length=len(answer),
            usage=output.metadata.get("usage"),
            cost=output.metadata.get("cost"),
        )
        return answer

    # -- Tier handlers -----------------------------------------------------

    async def _ask_direct(
        self,
        question: str,
        *,
        on_event: EventCallback | None,
        log: Any,
    ) -> tuple[str | None, str]:
        """Tier.DIRECT — single LLM call, no tools, no data."""
        run_id = new_run_id()
        log = log.bind(run_id=run_id)
        log.info("direct_start")

        emit = on_event or _noop_event
        provider = self._provider_factory.create(self._default_provider)

        messages: list[Message] = [
            Message(
                role="system",
                content=(
                    self._query_system_prompt
                    or "You are a helpful assistant. Be concise."
                ),
            ),
            Message(role="user", content=question),
        ]

        response = await provider.complete(
            model=self._default_model,
            messages=messages,
            temperature=0.3,
            max_tokens=1024,
        )

        answer = response.content or ""
        await emit("done", {"tier": "direct", "model": self._default_model})
        log.info("direct_done", answer_length=len(answer))
        return answer, run_id

    async def _ask_query(
        self,
        question: str,
        decision: RoutingDecision,
        *,
        on_event: EventCallback | None,
        log: Any,
    ) -> tuple[str | None, str]:
        """Tier.QUERY — fetch data in-process, format with one LLM call."""
        run_id = new_run_id()
        log = log.bind(run_id=run_id, operation=decision.operation)
        log.info("query_start")

        assert self._data_resolver is not None
        provider = self._provider_factory.create(self._default_provider)

        answer, metadata = await run_query_path(
            question=question,
            operation=decision.operation,
            params=decision.params,
            resolver=self._data_resolver,
            provider=provider,
            model=self._default_model,
            system_preamble=self._query_system_prompt,
            on_event=on_event,
        )

        log.info("query_done", answer_length=len(answer), **metadata)
        return answer, run_id

    async def _ask_agent(
        self,
        agent_name: str,
        question: str,
        *,
        on_event: EventCallback | None,
    ) -> tuple[str | None, str]:
        """Tier.AGENT — full agent loop with sandbox and tools."""
        run_id = new_run_id()
        log = logger.bind(run_id=run_id, agent=agent_name, tier="agent")
        log.info("ask_start", question_length=len(question))

        sandbox_sid = f"ask-{run_id}"
        await self._ensure_sandbox_session(sandbox_sid)

        params = RunParams(mode="agent", sandbox_session_id=sandbox_sid, on_event=on_event)
        ctx = self._build_context(run_id=run_id, params=params)

        try:
            config_dict, _runtime_cfg = self._load_agent_config(agent_name)
            config_dict["name"] = agent_name
            node = AgentNode(config=config_dict)
            output = await self._retry.execute(node.run, {"input": question}, ctx)

            answer = _extract_answer(output.value)
            log.info(
                "ask_done",
                answer_length=len(answer) if answer else 0,
                usage=output.metadata.get("usage"),
                cost=output.metadata.get("cost"),
            )
            return (answer, run_id)
        finally:
            await self._sandbox.destroy_session(sandbox_sid)

    async def _ask_session(
        self,
        session_id: str,
        question: str,
        *,
        on_event: EventCallback | None,
    ) -> tuple[str | None, str]:
        """Session-aware multi-turn — always uses the agent loop."""
        session = await self.sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)

        await self.sessions.append_message(
            session_id,
            ChatMessage(role="user", content=question),
        )
        refreshed = await self.sessions.get(session_id)
        thread = list(refreshed.thread) if refreshed else []

        answer = await self.run_chat_agent(
            session.agent,
            thread,
            on_event,
            sandbox_session_id=session.sandbox_session_id,
            provider=session.provider,
            model=session.model,
        )

        await self.sessions.append_message(
            session_id,
            ChatMessage(role="assistant", content=answer),
        )
        run_id = new_run_id()
        return (answer, run_id)

    # -- Internal helpers --------------------------------------------------

    def _classify(
        self, question: str, *, manager_id: str | None = None,
    ) -> RoutingDecision:
        if self._router is None:
            return RoutingDecision(tier=Tier.AGENT)
        return self._router.classify(question, manager_id=manager_id)

    def _load_agent_config(
        self,
        agent_name: str,
    ) -> tuple[dict[str, Any], RuntimeConfig]:
        """Load agent module config and runtime topology from app.yaml."""
        app_path = get_manifest_path(agent_name)
        if not app_path.exists():
            raise ValueError(f"Unknown agent: {agent_name!r} (looked in {app_path})")
        from remi.agent.workflow.loader import load_manifest_runtime

        runtime_cfg = load_manifest_runtime(agent_name, manifest_path=app_path)
        with open(app_path) as f:
            data: dict[str, Any] = yaml.safe_load(f)
        for module in data.get("modules", []):
            if module.get("kind") == "agent":
                cfg: dict[str, Any] = module.get("config", {})
                return cfg, runtime_cfg
        raise ValueError(f"No agent module found in {app_path}")

    def _build_context(
        self,
        run_id: str | None = None,
        *,
        params: RunParams | None = None,
        scope: ScopeContext | None = None,
        extra: dict[str, Any] | None = None,
    ) -> RuntimeContext:
        deps = RunDeps(
            provider_factory=self._provider_factory,
            tool_registry=self._tool_registry,
            tracer=self._tracer,
            usage_ledger=self._usage_ledger,
            memory_store=self._memory_store,
            recall_service=self._recall_service,
            domain_tbox=self._domain_tbox,
            context_builder=self._context_builder,
            default_provider=self._default_provider,
            default_model=self._default_model,
        )
        merged_extras = {"sandbox": self._sandbox}
        if extra:
            merged_extras.update(extra)
        return RuntimeContext(
            app_id="remi",
            run_id=run_id or new_run_id(),
            deps=deps,
            params=params or RunParams(),
            scope=scope or ScopeContext(),
            extras=merged_extras,
        )

    async def _ensure_sandbox_session(self, session_id: str) -> None:
        session = await self._sandbox.get_session(session_id)
        if session is None:
            await self._sandbox.create_session(session_id)


async def _noop_event(_type: str, _data: dict[str, Any]) -> None:
    pass


def _extract_answer(output: Any) -> str | None:
    """Pull the last assistant message from an agent output."""
    if isinstance(output, str):
        return output
    if isinstance(output, list):
        for msg in reversed(output):
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                content: str | None = msg.get("content", "")
                return content
        return json.dumps(output, default=str)
    if output is not None:
        return json.dumps(output, default=str)
    return None
