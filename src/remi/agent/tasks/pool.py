"""TaskPool — bounded concurrency for delegated agent tasks.

Defines the ``TaskPool`` protocol and the ``LocalTaskPool`` implementation
that uses asyncio primitives for single-process execution.

The pool is the execution backend for ``TaskSupervisor``. Swapping the
pool changes where tasks run without changing the supervisor's logic.
"""

from __future__ import annotations

import abc
import asyncio
from collections.abc import Awaitable, Callable

import structlog

from remi.agent.tasks.result import TaskResult
from remi.agent.tasks.task import Task

logger = structlog.get_logger(__name__)

TaskRunner = Callable[[Task], Awaitable[TaskResult]]


class TaskPool(abc.ABC):
    """Execution backend for agent tasks — submit, cancel, observe.

    Implementations control *where* tasks run: same process (local),
    a Redis-backed worker fleet, or a durable execution engine.
    """

    @property
    @abc.abstractmethod
    def active_count(self) -> int: ...

    @property
    @abc.abstractmethod
    def max_concurrency(self) -> int: ...

    @abc.abstractmethod
    async def submit(self, task: Task, runner: TaskRunner) -> None:
        """Schedule a task for execution. May block if at capacity."""

    @abc.abstractmethod
    async def cancel(self, task_id: str) -> bool:
        """Cancel a running task. Returns True if found and cancelled."""

    @abc.abstractmethod
    async def cancel_all(self) -> int:
        """Cancel all running tasks. Returns the count cancelled."""

    @abc.abstractmethod
    async def wait_all(self, timeout: float | None = None) -> None:
        """Wait for all active tasks to complete."""


class LocalTaskPool(TaskPool):
    """In-process task pool using asyncio semaphore + tasks.

    Good for single-process deployments and development. Tasks execute
    on the current event loop with bounded concurrency.
    """

    def __init__(self, max_concurrency: int = 4) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._max = max_concurrency
        self._active: dict[str, asyncio.Task[None]] = {}

    @property
    def active_count(self) -> int:
        return len(self._active)

    @property
    def max_concurrency(self) -> int:
        return self._max

    async def submit(self, task: Task, runner: TaskRunner) -> None:
        await self._semaphore.acquire()
        aio_task = asyncio.create_task(self._run(task, runner))
        self._active[task.id] = aio_task
        aio_task.add_done_callback(lambda _: self._cleanup(task.id))

    async def _run(self, task: Task, runner: TaskRunner) -> None:
        try:
            task.mark_running()
            timeout = task.spec.constraints.timeout_seconds
            if timeout is not None:
                result = await asyncio.wait_for(runner(task), timeout=timeout)
            else:
                result = await runner(task)
            task.mark_done(result)
        except TimeoutError:
            logger.warning(
                "task_timeout",
                task_id=task.id,
                agent=task.spec.agent_name,
                timeout=task.spec.constraints.timeout_seconds,
            )
            task.mark_failed(
                TaskResult.failure(
                    f"Task timed out after {task.spec.constraints.timeout_seconds}s",
                    run_id=task.id,
                )
            )
        except asyncio.CancelledError:
            task.mark_cancelled()
        except Exception as exc:
            logger.error(
                "task_runner_error",
                task_id=task.id,
                agent=task.spec.agent_name,
                exc_info=True,
            )
            task.mark_failed(TaskResult.failure(str(exc), run_id=task.id))
        finally:
            self._semaphore.release()

    def _cleanup(self, task_id: str) -> None:
        self._active.pop(task_id, None)

    async def cancel(self, task_id: str) -> bool:
        aio_task = self._active.get(task_id)
        if aio_task is None:
            return False
        aio_task.cancel()
        return True

    async def cancel_all(self) -> int:
        count = 0
        for aio_task in list(self._active.values()):
            aio_task.cancel()
            count += 1
        return count

    async def wait_all(self, timeout: float | None = None) -> None:
        if not self._active:
            return
        await asyncio.wait(
            list(self._active.values()),
            timeout=timeout,
        )
