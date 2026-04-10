"""Task — lifecycle state machine for a unit of delegated work.

A Task wraps a TaskSpec with runtime state: when it started, when it
finished, what it produced, and how many resources it consumed. The
supervisor owns Task instances; parent agents hold handles to them.

Lifecycle::

    pending → running → done | failed | cancelled
                ↓
         waiting_on_human → running  (resumed with human answers)
"""

from __future__ import annotations

import asyncio
import enum
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from remi.agent.tasks.result import TaskResult
from remi.agent.tasks.spec import HumanQuestion, TaskSpec


class TaskStatus(enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_ON_HUMAN = "waiting_on_human"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """A supervised unit of delegated work with lifecycle tracking.

    Created by the supervisor when a TaskSpec is submitted. Transitions
    through ``pending → running → done|failed|cancelled``, with an
    optional ``waiting_on_human`` suspension when the task needs user input.
    """

    id: str
    spec: TaskSpec
    status: TaskStatus = TaskStatus.PENDING
    result: TaskResult | None = None
    created_at: float = field(default_factory=time.monotonic)
    started_at: float | None = None
    finished_at: float | None = None
    human_questions: list[HumanQuestion] = field(default_factory=list)
    human_answers: dict[str, Any] = field(default_factory=dict)

    _done_event: asyncio.Event = field(default_factory=asyncio.Event, repr=False, compare=False)
    _human_event: asyncio.Event = field(default_factory=asyncio.Event, repr=False, compare=False)

    @staticmethod
    def create(spec: TaskSpec) -> Task:
        return Task(id=f"task-{uuid4().hex[:12]}", spec=spec)

    @property
    def is_terminal(self) -> bool:
        return self.status in (TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED)

    @property
    def elapsed_ms(self) -> float | None:
        if self.started_at is None:
            return None
        end = self.finished_at or time.monotonic()
        return round((end - self.started_at) * 1000, 1)

    def mark_running(self) -> None:
        self.status = TaskStatus.RUNNING
        self.started_at = time.monotonic()

    def mark_waiting_on_human(self, questions: list[HumanQuestion]) -> None:
        """Suspend the task until a human provides answers."""
        self.status = TaskStatus.WAITING_ON_HUMAN
        self.human_questions = questions
        self._human_event.clear()

    def supply_human_answers(self, answers: dict[str, Any]) -> None:
        """Resume a suspended task with the human's answers."""
        self.human_answers.update(answers)
        self.status = TaskStatus.RUNNING
        self._human_event.set()

    async def wait_for_human(self, timeout: float | None = None) -> dict[str, Any]:
        """Block until human answers arrive. Used by the tool implementation."""
        await asyncio.wait_for(self._human_event.wait(), timeout=timeout)
        return self.human_answers

    def mark_done(self, result: TaskResult) -> None:
        self.status = TaskStatus.DONE
        self.result = result
        self.finished_at = time.monotonic()
        self._done_event.set()

    def mark_failed(self, result: TaskResult) -> None:
        self.status = TaskStatus.FAILED
        self.result = result
        self.finished_at = time.monotonic()
        self._done_event.set()

    def mark_cancelled(self) -> None:
        self.status = TaskStatus.CANCELLED
        self.result = TaskResult.failure("cancelled")
        self.finished_at = time.monotonic()
        self._done_event.set()

    async def wait(self, timeout: float | None = None) -> TaskResult:
        """Block until the task reaches a terminal state.

        Raises ``asyncio.TimeoutError`` if ``timeout`` is exceeded.
        """
        if self.is_terminal and self.result is not None:
            return self.result
        await asyncio.wait_for(self._done_event.wait(), timeout=timeout)
        assert self.result is not None  # noqa: S101
        return self.result
