"""Supervisor — schedules tasks, enforces budgets, publishes lifecycle events.

The supervisor is the kernel's multi-agent coordinator. It accepts
TaskSpecs from parent agents (via the delegation tool), spawns them
into the TaskPool, tracks their lifecycle, and publishes domain events
so the rest of the system can observe task activity.

This replaces the direct ``AgentInvoker.ask()`` call that delegation
used before — adding lifecycle tracking, budget enforcement, trace
correlation, and structured output.
"""

from __future__ import annotations

from typing import Any, Protocol

import structlog

from remi.agent.events.bus import EventBus
from remi.agent.events.envelope import DomainEvent
from remi.agent.tasks.pool import LocalTaskPool, TaskPool
from remi.agent.tasks.result import TaskResult
from remi.agent.tasks.spec import TaskSpec
from remi.agent.tasks.task import Task, TaskStatus

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
    ) -> tuple[str | None, str]: ...


class TaskSupervisor:
    """Kernel-level task scheduler for multi-agent delegation.

    Responsibilities:
      - Accept TaskSpecs and create tracked Task instances
      - Execute tasks through the pool with bounded concurrency
      - Publish lifecycle events (task.spawned, task.completed, task.failed)
      - Track all tasks for observability and parent-agent queries
      - Enforce aggregate budgets (future: per-parent token caps)
    """

    def __init__(
        self,
        executor: AgentExecutor,
        event_bus: EventBus | None = None,
        pool: TaskPool | None = None,
        max_concurrency: int = 4,
    ) -> None:
        self._executor = executor
        self._event_bus = event_bus
        self._pool = pool or LocalTaskPool(max_concurrency=max_concurrency)
        self._tasks: dict[str, Task] = {}

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

    async def spawn(self, spec: TaskSpec) -> Task:
        """Submit a task for supervised execution. Returns immediately.

        The task is created in PENDING state, then submitted to the pool.
        Callers can ``await task.wait()`` for the result, or poll
        ``task.status``.
        """
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
        """Run the agent and produce a TaskResult."""
        spec = task.spec
        log = logger.bind(
            task_id=task.id,
            agent=spec.agent_name,
            parent_run_id=spec.parent_run_id,
        )

        prompt = spec.objective
        if spec.input_data:
            import json
            data_str = json.dumps(spec.input_data, default=str)
            prompt = f"{spec.objective}\n\n## Input data\n{data_str}"

        log.info("task_executing", prompt_length=len(prompt))

        try:
            answer, run_id = await self._executor.ask(
                spec.agent_name,
                prompt,
                mode="agent",
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

    async def shutdown(self) -> None:
        """Cancel all active tasks and wait for them to finish."""
        if self._pool.active_count > 0:
            logger.info("supervisor_shutdown", active=self._pool.active_count)
            await self._pool.cancel_all()
            await self._pool.wait_all(timeout=5.0)
