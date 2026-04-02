"""Retry policy for module execution.

LLM provider SDKs handle transport-level retries internally.  This
policy is for *application-level* recovery — e.g. retrying the whole
agent run when a transient infrastructure error causes the run to fail.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

import structlog

from remi.agent.observe.events import Event
from remi.types.errors import (
    LLMConnectionError,
    LLMRateLimitError,
    LLMTimeoutError,
    RetryExhaustedError,
)

T = TypeVar("T")

logger = structlog.get_logger("remi.retry")


def _default_transient_exceptions() -> tuple[type[Exception], ...]:
    return (
        ConnectionError,
        TimeoutError,
        OSError,
        LLMConnectionError,
        LLMTimeoutError,
        LLMRateLimitError,
    )


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 2
    delay_seconds: float = 2.0
    backoff_multiplier: float = 2.0
    retryable_exceptions: tuple[type[Exception], ...] = field(
        default_factory=_default_transient_exceptions,
    )

    async def execute(self, fn: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any) -> T:
        last_exception: Exception | None = None
        delay = self.delay_seconds

        for attempt in range(1, self.max_retries + 1):
            try:
                return await fn(*args, **kwargs)
            except self.retryable_exceptions as exc:
                last_exception = exc
                logger.warning(
                    Event.RETRY_ATTEMPT,
                    attempt=attempt,
                    max_retries=self.max_retries,
                    error=str(exc),
                    error_type=type(exc).__name__,
                    next_delay=delay if attempt < self.max_retries else None,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(delay)
                    delay *= self.backoff_multiplier

        logger.error(
            Event.RETRY_EXHAUSTED,
            max_retries=self.max_retries,
            error=str(last_exception),
            error_type=type(last_exception).__name__ if last_exception else None,
        )
        raise RetryExhaustedError(
            f"All {self.max_retries} retry attempts failed: {last_exception}",
            attempts=self.max_retries,
            last_error=last_exception,
        ) from last_exception
