"""Supervisor — schedules tasks, enforces budgets, publishes lifecycle events.

The supervisor is the kernel's unified task dispatcher. It accepts
TaskSpecs from any caller (parent agents via the delegation tool,
API routes, CLI commands), resolves the manifest ``kind`` (Agent,
Pipeline, Workflow), and routes execution to the right engine:

  - ``kind: Agent`` → ``AgentExecutor.ask()``
  - ``kind: Pipeline`` / ``kind: Workflow`` → ``WorkflowExecutor.run()``

This is the **single dispatch point** for all AI work in the OS.
Application code never calls ``AgentRuntime.ask()`` or
``WorkflowRunner.run()`` directly — it submits a ``TaskSpec`` to the
supervisor.

The supervisor is also the enforcement point for delegation access
control, lifecycle tracking, and budget enforcement.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

import structlog

from remi.agent.events.bus import EventBus
from remi.agent.events.envelope import DomainEvent
from remi.agent.runtime.config import Placement
from remi.agent.tasks.pool import LocalTaskPool, TaskPool
from remi.agent.tasks.result import TaskResult, TaskUsage
from remi.agent.tasks.spec import HumanQuestion, TaskSpec
from remi.agent.tasks.task import Task, TaskStatus
from remi.agent.workforce import Workforce
from remi.agent.workflow.registry import get_manifest_kind

logger = structlog.get_logger(__name__)


class AgentExecutor(Protocol):
    """The capability to run a named agent and get a result.

    Implemented by ``AgentRuntime`` — the supervisor doesn't know
    about LLMs, providers, or tool registries. It only knows how to
    submit a name + prompt and get back an answer + run_id.
    """

    async def ask(
        self,
        agent_name: str,
        question: str,
        *,
        session_id: str | None = None,
        mode: str = "agent",
        task_id: str | None = None,
    ) -> tuple[str | None, str]: ...


class WorkflowExecutor(Protocol):
    """The capability to run a named workflow and get structured output.

    Implemented by a thin adapter around ``WorkflowRunner`` — the
    supervisor doesn't know about LLM providers or step types.
    """

    async def run_workflow(
        self,
        workflow_name: str,
        workflow_input: str,
        *,
        context: dict[str, str] | None = None,
        task_id: str | None = None,
    ) -> WorkflowExecutorResult: ...


class WorkflowExecutorResult(Protocol):
    """Minimal result interface returned by WorkflowExecutor."""

    def step(self, step_id: str) -> Any: ...

    @property
    def total_usage(self) -> Any: ...

    @property
    def steps(self) -> Any: ...


class TaskSupervisor:
    """Kernel-level task dispatcher for agents and workflows.

    Responsibilities:
      - Accept TaskSpecs and create tracked Task instances
      - **Resolve manifest kind** and route to the right executor
      - **Enforce delegation ACLs** via the Workforce graph
      - Execute tasks through the pool with bounded concurrency
      - Publish lifecycle events (task.spawned, task.completed, task.failed)
      - Track all tasks for observability and parent-agent queries
    """

    def __init__(
        self,
        executor: AgentExecutor,
        event_bus: EventBus | None = None,
        pool: TaskPool | None = None,
        max_concurrency: int = 4,
        workforce: Workforce | None = None,
        workflow_executor: WorkflowExecutor | None = None,
    ) -> None:
        self._executor = executor
        self._workflow_executor = workflow_executor
        self._event_bus = event_bus
        self._pool = pool or LocalTaskPool(max_concurrency=max_concurrency)
        self._tasks: dict[str, Task] = {}
        self._workforce = workforce

    def update_workforce(self, workforce: Workforce) -> None:
        """Replace the workforce graph used for delegation ACL checks.

        Called after new manifests are discovered post-boot.
        """
        self._workforce = workforce

    @property
    def active_count(self) -> int:
        return self._pool.active_count

    @property
    def total_tasks(self) -> int:
        return len(self._tasks)

    def get_task(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def list_tasks(
        self,
        *,
        parent_run_id: str | None = None,
        status: TaskStatus | None = None,
    ) -> list[Task]:
        """List tasks, optionally filtered by parent or status."""
        tasks = list(self._tasks.values())
        if parent_run_id is not None:
            tasks = [t for t in tasks if t.spec.parent_run_id == parent_run_id]
        if status is not None:
            tasks = [t for t in tasks if t.status == status]
        return tasks

    def _validate_delegation(self, spec: TaskSpec) -> str | None:
        """Check the workforce graph for a valid delegation edge.

        Returns an error message if the delegation is disallowed,
        or ``None`` if it is permitted.

        When no workforce is set, all delegations are allowed (backward
        compat for single-agent deployments and tests).
        """
        if self._workforce is None:
            return None

        caller = spec.metadata.get("caller", "")
        if not caller:
            return None

        allowed = self._workforce.get_delegates(caller)
        if not allowed and not self._workforce.get_agent(caller):
            return None

        if spec.agent_name not in allowed:
            return (
                f"Agent '{caller}' is not allowed to delegate to "
                f"'{spec.agent_name}'. Declared delegates: {list(allowed.keys())}"
            )
        return None

    def _resolve_kind(self, name: str) -> str:
        """Resolve the manifest kind for a given task name.

        Falls back to "Agent" if the manifest is not registered
        (e.g. tests without full bootstrap).
        """
        try:
            return get_manifest_kind(name)
        except ValueError:
            return "Agent"

    async def spawn(self, spec: TaskSpec) -> Task:
        """Submit a task for supervised execution. Returns immediately.

        The task is created in PENDING state, then submitted to the pool.
        Callers can ``await task.wait()`` for the result, or poll
        ``task.status``.

        If a ``Workforce`` is configured, the supervisor validates the
        delegation edge before accepting the task.
        """
        denial = self._validate_delegation(spec)
        if denial is not None:
            logger.warning(
                "delegation_denied",
                caller=spec.metadata.get("caller", ""),
                target=spec.agent_name,
                reason=denial,
            )
            task = Task.create(spec)
            result = TaskResult.failure(
                denial,
                agent=spec.agent_name,
                parent_run_id=spec.parent_run_id,
            )
            task.mark_done(result)
            self._tasks[task.id] = task
            await self._publish("task.denied", task)
            return task

        task = Task.create(spec)
        self._tasks[task.id] = task

        log = logger.bind(
            task_id=task.id,
            agent=spec.agent_name,
            parent_run_id=spec.parent_run_id,
        )
        log.info(
            "task_spawned",
            objective_length=len(spec.objective),
            has_constraints=spec.constraints != spec.constraints.__class__(),
        )

        await self._publish("task.spawned", task)
        await self._pool.submit(task, self._execute)
        return task

    async def spawn_and_wait(
        self,
        spec: TaskSpec,
        timeout: float | None = None,
    ) -> TaskResult:
        """Submit a task and block until it completes (or times out).

        Convenience method for synchronous-style delegation where the
        parent agent needs the result before continuing.
        """
        task = await self.spawn(spec)
        return await task.wait(timeout=timeout)

    async def suspend_for_human(
        self, task_id: str, questions: list[HumanQuestion],
    ) -> bool:
        """Suspend a running task until a human answers the questions.

        Returns True if the task was found and suspended.  The task
        transitions to ``WAITING_ON_HUMAN`` and a ``task.waiting_on_human``
        event is published with the questions payload for the frontend.
        """
        task = self._tasks.get(task_id)
        if task is None or task.status != TaskStatus.RUNNING:
            return False

        task.mark_waiting_on_human(questions)
        logger.info(
            "task_waiting_on_human",
            task_id=task_id,
            question_count=len(questions),
            agent=task.spec.agent_name,
        )
        await self._publish_human_request(task, questions)
        return True

    async def supply_human_answers(
        self, task_id: str, answers: dict[str, Any],
    ) -> bool:
        """Resume a suspended task with the human's answers.

        Returns True if the task was found in ``WAITING_ON_HUMAN`` state
        and resumed. Publishes ``task.human_answered``.
        """
        task = self._tasks.get(task_id)
        if task is None or task.status != TaskStatus.WAITING_ON_HUMAN:
            return False

        task.supply_human_answers(answers)
        logger.info(
            "task_human_answered",
            task_id=task_id,
            answer_keys=list(answers.keys()),
            agent=task.spec.agent_name,
        )
        await self._publish("task.human_answered", task)
        return True

    async def cancel(self, task_id: str) -> bool:
        """Cancel a task by id. Returns True if found and cancelled."""
        task = self._tasks.get(task_id)
        if task is None:
            return False
        if task.is_terminal:
            return False

        cancelled = await self._pool.cancel(task_id)
        if not cancelled and not task.is_terminal:
            task.mark_cancelled()

        logger.info("task_cancelled", task_id=task_id, agent=task.spec.agent_name)
        await self._publish("task.cancelled", task)
        return True

    async def cancel_children(self, parent_run_id: str) -> int:
        """Cancel all non-terminal tasks spawned by a given parent run."""
        children = self.list_tasks(parent_run_id=parent_run_id)
        count = 0
        for child in children:
            if not child.is_terminal:
                await self.cancel(child.id)
                count += 1
        return count

    async def _execute(self, task: Task) -> TaskResult:
        """Route to the right executor based on manifest kind."""
        kind = self._resolve_kind(task.spec.agent_name)
        if kind in ("Pipeline", "Workflow") and self._workflow_executor is not None:
            return await self._execute_workflow(task)
        return await self._execute_agent(task)

    def _resolve_executor(self, agent_name: str) -> AgentExecutor:
        """Pick the right executor based on the agent's declared placement.

        INLINE / WORKER / CONTAINER → local executor (current behavior).
        SERVICE → RemoteAgentExecutor pointing at the agent's endpoint.
        """
        if self._workforce is None:
            return self._executor

        desc = self._workforce.get_agent(agent_name)
        if desc is None or desc.runtime.placement != Placement.SERVICE:
            return self._executor

        endpoint = desc.runtime.endpoint
        if not endpoint:
            logger.warning(
                "service_placement_no_endpoint",
                agent=agent_name,
                msg="placement is 'service' but no endpoint configured; falling back to local",
            )
            return self._executor

        from remi.agent.tasks.adapters.remote import RemoteAgentExecutor

        timeout = desc.runtime.resources.timeout_seconds or 300.0
        return RemoteAgentExecutor(base_url=endpoint, timeout=timeout)

    async def _execute_agent(self, task: Task) -> TaskResult:
        """Run an agent and produce a TaskResult."""
        spec = task.spec
        log = logger.bind(
            task_id=task.id,
            agent=spec.agent_name,
            parent_run_id=spec.parent_run_id,
        )

        prompt = spec.objective
        if spec.input_data:
            data_str = json.dumps(spec.input_data, default=str)
            prompt = f"{spec.objective}\n\n## Input data\n{data_str}"

        executor = self._resolve_executor(spec.agent_name)
        placement = "local"
        if executor is not self._executor:
            placement = "remote"
        log.info("task_executing", prompt_length=len(prompt), kind="Agent", placement=placement)

        try:
            answer, run_id = await executor.ask(
                spec.agent_name,
                prompt,
                mode="agent",
                task_id=task.id,
            )
            result = TaskResult.success(
                answer,
                run_id=run_id,
                agent=spec.agent_name,
                parent_run_id=spec.parent_run_id,
            )
            log.info(
                "task_completed",
                run_id=run_id,
                answer_length=len(answer) if answer else 0,
            )
            await self._publish("task.completed", task)
            return result

        except Exception as exc:
            log.error("task_execution_failed", exc_info=True)
            result = TaskResult.failure(
                str(exc),
                agent=spec.agent_name,
                parent_run_id=spec.parent_run_id,
            )
            await self._publish("task.failed", task)
            return result

    async def _execute_workflow(self, task: Task) -> TaskResult:
        """Run a workflow/pipeline and pack the result into a TaskResult."""
        spec = task.spec
        log = logger.bind(
            task_id=task.id,
            workflow=spec.agent_name,
            parent_run_id=spec.parent_run_id,
        )

        assert self._workflow_executor is not None

        workflow_input = spec.objective
        if spec.input_data:
            workflow_input = json.dumps(spec.input_data, default=str)

        context = spec.metadata.get("workflow_context")
        if context is not None and not isinstance(context, dict):
            context = None

        log.info("task_executing_workflow", input_length=len(workflow_input), kind="Workflow")

        try:
            wf_result = await self._workflow_executor.run_workflow(
                spec.agent_name,
                workflow_input,
                context=context,
                task_id=task.id,
            )

            step_data: dict[str, Any] = {}
            for sr in wf_result.steps:
                step_data[sr.step_id] = sr.value

            usage_raw = wf_result.total_usage
            usage = TaskUsage(
                prompt_tokens=getattr(usage_raw, "prompt_tokens", 0),
                completion_tokens=getattr(usage_raw, "completion_tokens", 0),
                total_tokens=(
                    getattr(usage_raw, "prompt_tokens", 0)
                    + getattr(usage_raw, "completion_tokens", 0)
                ),
            )

            result = TaskResult.success(
                output=json.dumps(step_data, default=str),
                data=step_data,
                run_id=task.id,
                usage=usage,
                agent=spec.agent_name,
                parent_run_id=spec.parent_run_id,
            )
            log.info(
                "task_completed",
                steps_count=len(step_data),
            )
            await self._publish("task.completed", task)
            return result

        except Exception as exc:
            log.error("workflow_execution_failed", exc_info=True)
            result = TaskResult.failure(
                str(exc),
                agent=spec.agent_name,
                parent_run_id=spec.parent_run_id,
            )
            await self._publish("task.failed", task)
            return result

    async def _publish(self, topic: str, task: Task) -> None:
        """Publish a task lifecycle event to the event bus."""
        if self._event_bus is None:
            return

        payload: dict[str, Any] = {
            "task_id": task.id,
            "agent_name": task.spec.agent_name,
            "status": task.status.value,
            "parent_run_id": task.spec.parent_run_id,
        }
        if task.elapsed_ms is not None:
            payload["elapsed_ms"] = task.elapsed_ms
        if task.result is not None:
            payload["ok"] = task.result.ok
            if task.result.error:
                payload["error"] = task.result.error

        await self._event_bus.publish(
            DomainEvent(
                topic=topic,
                payload=payload,
                source="task_supervisor",
            )
        )

    async def _publish_human_request(
        self, task: Task, questions: list[HumanQuestion],
    ) -> None:
        """Publish a task.waiting_on_human event with structured questions."""
        if self._event_bus is None:
            return

        questions_payload = [
            {
                "id": q.id,
                "prompt": q.prompt,
                "kind": q.kind,
                "options": [{"id": o.id, "label": o.label} for o in q.options],
                "default": q.default,
                "required": q.required,
            }
            for q in questions
        ]

        await self._event_bus.publish(
            DomainEvent(
                topic="task.waiting_on_human",
                payload={
                    "task_id": task.id,
                    "agent_name": task.spec.agent_name,
                    "parent_run_id": task.spec.parent_run_id,
                    "questions": questions_payload,
                    "document_id": task.spec.metadata.get("document_id", ""),
                },
                source="task_supervisor",
            )
        )

    async def shutdown(self) -> None:
        """Cancel all active tasks and wait for them to finish."""
        if self._pool.active_count > 0:
            logger.info("supervisor_shutdown", active=self._pool.active_count)
            await self._pool.cancel_all()
            await self._pool.wait_all(timeout=5.0)
