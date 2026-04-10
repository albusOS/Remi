"""CLI output helpers — re-exported from ``application.cli_output``.

The canonical implementation lives in ``remi.application.cli_output``
so that application-layer CLI slices can import without crossing into
the shell ring.  This module re-exports for backward compatibility.
"""

from remi.application.cli_output import (
    emit,
    emit_error,
    emit_success,
    error,
    success,
)

__all__ = [
    "emit",
    "emit_error",
    "emit_success",
    "error",
    "success",
]
