"""Result monad for explicit error handling without exceptions in domain logic.

Usage::

    from remi.types.result import Ok, Err, Result

    def divide(a: float, b: float) -> Result[float, str]:
        if b == 0:
            return Err("division by zero")
        return Ok(a / b)

    match divide(10, 0):
        case Ok(value):
            print(f"Result: {value}")
        case Err(error):
            print(f"Failed: {error}")
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Generic, TypeVar

T = TypeVar("T")
E = TypeVar("E")


@dataclass(frozen=True, slots=True)
class Ok(Generic[T]):
    value: T

    @property
    def is_ok(self) -> bool:
        return True

    @property
    def is_err(self) -> bool:
        return False

    def unwrap(self) -> T:
        return self.value

    def unwrap_err(self) -> None:
        raise RuntimeError("Called unwrap_err on Ok")


@dataclass(frozen=True, slots=True)
class Err(Generic[E]):
    error: E

    @property
    def is_ok(self) -> bool:
        return False

    @property
    def is_err(self) -> bool:
        return True

    def unwrap(self) -> None:
        raise RuntimeError(f"Called unwrap on Err: {self.error}")

    def unwrap_err(self) -> E:
        return self.error


Result = Ok[T] | Err[E]


class WriteOutcome(StrEnum):
    """Discriminator for idempotent write operations.

    Returned by repository upserts so callers can distinguish "created a new
    entity" from "merged into an existing one" without a separate read.
    """

    CREATED = "created"
    UPDATED = "updated"
    NOOP = "noop"


@dataclass(frozen=True, slots=True)
class WriteResult(Generic[T]):
    """Result of an idempotent write: the persisted entity + what happened."""

    entity: T
    outcome: WriteOutcome
