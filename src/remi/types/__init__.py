"""Pure vocabulary — ids, clock, errors, enums, result, text. No I/O.

Re-exports the most-used types so consumers can write::

    from remi.types import RemiSettings, RemiError, Clock, Ok, Err
"""

from remi.types.clock import Clock, FixedClock, SystemClock
from remi.types.config import RemiSettings
from remi.types.errors import (
    DomainError,
    ExecutionError,
    NotFoundError,
    RemiError,
    ValidationError,
)
from remi.types.ids import AppId, EdgeId, ModuleId, RunId, new_edge_id, new_run_id
from remi.types.result import Err, Ok, Result, WriteOutcome, WriteResult

__all__ = [
    "AppId",
    "Clock",
    "DomainError",
    "EdgeId",
    "Err",
    "ExecutionError",
    "FixedClock",
    "ModuleId",
    "NotFoundError",
    "Ok",
    "RemiError",
    "RemiSettings",
    "Result",
    "RunId",
    "SystemClock",
    "ValidationError",
    "WriteOutcome",
    "WriteResult",
    "new_edge_id",
    "new_run_id",
]
