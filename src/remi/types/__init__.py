"""Pure vocabulary — ids, clock, errors, enums, result, text. No I/O.

Re-exports the most-used types so consumers can write::

    from remi.types import RemiError, Clock, Ok, Err
"""

from remi.types.clock import Clock, FixedClock, SystemClock
from remi.types.errors import (
    DomainError,
    ExecutionError,
    NotFoundError,
    RemiError,
    ValidationError,
)
from remi.types.ids import (
    AppId,
    EdgeId,
    ModuleId,
    RunId,
    WorkspaceId,
    new_edge_id,
    new_run_id,
)
from remi.types.coerce import to_date, to_decimal, to_decimal_or_none, to_int
from remi.types.result import Err, Ok, Result, WriteOutcome, WriteResult

__all__ = [
    "AppId",
    "Clock",
    "to_date",
    "to_decimal",
    "to_decimal_or_none",
    "to_int",
    "DomainError",
    "EdgeId",
    "Err",
    "ExecutionError",
    "FixedClock",
    "ModuleId",
    "NotFoundError",
    "Ok",
    "RemiError",
    "Result",
    "RunId",
    "SystemClock",
    "ValidationError",
    "WorkspaceId",
    "WriteOutcome",
    "WriteResult",
    "new_edge_id",
    "new_run_id",
]
