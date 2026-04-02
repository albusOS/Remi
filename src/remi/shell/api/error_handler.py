"""Global error-to-HTTP translation.

Every exception — ``RemiError``, ``HTTPException``, Pydantic validation,
or unhandled — is funnelled into a single JSON shape::

    {"error": {"code": "...", "message": "..."}}

This eliminates the client-side ambiguity between FastAPI's default
``{"detail": ...}`` and our ``{"error": ...}`` format.
"""

from __future__ import annotations

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from remi.observe.events import Event
from remi.types.errors import (
    AgentConfigError,
    AppNotFoundError,
    ConflictError,
    DomainError,
    ExecutionError,
    IngestionError,
    LLMError,
    NotFoundError,
    RemiError,
    RetryExhaustedError,
    SessionNotFoundError,
    ValidationError,
)

logger = structlog.get_logger("remi.error_handler")

_STATUS_MAP: list[tuple[type[RemiError], int]] = [
    (ValidationError, 422),
    (NotFoundError, 404),
    (AppNotFoundError, 404),
    (SessionNotFoundError, 404),
    (ConflictError, 409),
    (AgentConfigError, 400),
    (DomainError, 400),
    (RetryExhaustedError, 502),
    (LLMError, 502),
    (IngestionError, 500),
    (ExecutionError, 502),
    (RemiError, 500),
]


def _status_for(exc: RemiError) -> int:
    for err_type, status in _STATUS_MAP:
        if isinstance(exc, err_type):
            return status
    return 500


def _error_body(code: str, message: str) -> dict[str, object]:
    return {"error": {"code": code, "message": message}}


async def _handle_remi_error(request: Request, exc: RemiError) -> JSONResponse:
    status = _status_for(exc)
    logger.error(
        Event.HTTP_ERROR_RESPONSE,
        error_code=exc.code,
        error_type=type(exc).__name__,
        status_code=status,
        path=request.url.path,
        method=request.method,
        detail=str(exc),
    )
    return JSONResponse(status_code=status, content=_error_body(exc.code, str(exc)))


async def _handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    code = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
    }.get(exc.status_code, "HTTP_ERROR")
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(code, detail),
    )


async def _handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    messages = "; ".join(
        f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
    )
    return JSONResponse(
        status_code=422,
        content=_error_body("VALIDATION_ERROR", messages),
    )


async def _handle_unhandled(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        Event.UNHANDLED_ERROR,
        error_type=type(exc).__name__,
        path=request.url.path,
        method=request.method,
        detail=str(exc),
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content=_error_body("INTERNAL_ERROR", "Internal server error"),
    )


def install_error_handlers(app: FastAPI) -> None:
    """Register global exception handlers on *app*."""
    app.add_exception_handler(RemiError, _handle_remi_error)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, _handle_http_exception)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _handle_validation_error)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _handle_unhandled)
