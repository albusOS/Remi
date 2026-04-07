"""Task pool factory — build the right execution backend from settings.

``local`` is the default: asyncio semaphore in the current process.
``redis`` is the cross-process backend: tasks enqueued to a Redis list,
consumed by ``remi worker`` processes. Implementation is lazy-imported.
"""

from __future__ import annotations

import structlog

from remi.agent.tasks.pool import LocalTaskPool, TaskPool
from remi.types.config import TaskQueueSettings

logger = structlog.get_logger(__name__)


def build_task_pool(settings: TaskQueueSettings) -> TaskPool:
    """Construct the task pool backend selected by settings."""
    backend = settings.backend.lower()

    if backend == "local":
        logger.info("task_pool_backend", backend="local", concurrency=settings.max_concurrency)
        return LocalTaskPool(max_concurrency=settings.max_concurrency)

    if backend == "redis":
        raise NotImplementedError(
            "Redis task pool backend is defined as a protocol extension point. "
            "Implement ``RedisTaskPool(TaskPool)`` in ``agent/tasks/redis.py`` "
            "and register it here when distributed workers are needed."
        )

    raise ValueError(
        f"Unknown task pool backend: {backend!r}. "
        f"Supported: local, redis"
    )
