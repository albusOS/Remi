"""agent/tasks — supervised multi-agent delegation for the AI OS kernel.

A task is a unit of delegated work with a lifecycle. The supervisor
schedules tasks into a bounded pool, enforces budgets, correlates
traces, and publishes lifecycle events. This is the kernel primitive
that makes multi-agent coordination first-class.

Public API::

    from remi.agent.tasks import (
        TaskSpec, TaskConstraints,
        Task, TaskStatus,
        TaskResult, TaskUsage,
        TaskSupervisor, AgentExecutor,
        TaskPool,
    )
"""

from remi.agent.tasks.factory import build_task_pool
from remi.agent.tasks.pool import LocalTaskPool, TaskPool
from remi.agent.tasks.result import TaskResult, TaskUsage
from remi.agent.tasks.spec import TaskConstraints, TaskSpec
from remi.agent.tasks.supervisor import AgentExecutor, TaskSupervisor
from remi.agent.tasks.task import Task, TaskStatus

__all__ = [
    "AgentExecutor",
    "LocalTaskPool",
    "Task",
    "TaskConstraints",
    "TaskPool",
    "TaskResult",
    "TaskSpec",
    "TaskStatus",
    "TaskSupervisor",
    "TaskUsage",
    "build_task_pool",
]
