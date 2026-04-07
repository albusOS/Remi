"""FastAPI application factory.

``create_app()`` builds the standalone server used by ``remi serve``.
It creates its own Container in the lifespan and manages the full lifecycle.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from remi.agent.observe import Event, configure_logging
from remi.shell.api.error_handler import install_error_handlers
from remi.shell.api.middleware import RequestIDMiddleware
from remi.shell.config.capabilities import (
    all_capabilities,
    ensure_capabilities_registered,
    resolve_routers,
)
from remi.shell.config.settings import RemiSettings, load_settings


def _attach_routers(application: FastAPI) -> None:
    """Mount all routers from registered capabilities."""
    for cap in all_capabilities().values():
        routers = resolve_routers(cap)
        for router in routers:
            if cap.api_prefix:
                application.include_router(router, prefix=cap.api_prefix)
            else:
                application.include_router(router)


def _add_cors(application: FastAPI, settings: RemiSettings) -> None:
    origins = settings.api.cors_origins or ["http://localhost:3000"]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# -- Standalone server (``remi serve``) ------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    import asyncio

    import structlog

    from remi.shell.config.container import Container

    settings: RemiSettings = app.state.settings
    configure_logging(level=settings.logging.level, format=settings.logging.format)
    log = structlog.get_logger("remi.server")

    container = Container(settings=settings)
    app.state.container = container
    await container.ensure_bootstrapped()

    log.info(
        Event.SERVER_READY,
        provider=settings.llm.default_provider,
        model=settings.llm.default_model,
        tools=len(container.tool_registry.list_tools()),
        environment=settings.environment,
    )

    _reap_interval = 300

    async def _reap_loop() -> None:
        while True:
            await asyncio.sleep(_reap_interval)
            try:
                reaped = await container.sandbox.reap_expired_sessions()
                if reaped:
                    log.info("sandbox_sessions_reaped", count=reaped)
            except Exception:
                log.warning("sandbox_reap_error", exc_info=True)

    reap_task = asyncio.create_task(_reap_loop())

    yield

    reap_task.cancel()
    log.info(Event.SERVER_SHUTDOWN)


def create_app() -> FastAPI:
    ensure_capabilities_registered()

    settings = load_settings()
    application = FastAPI(
        title="REMI",
        description=(
            "Real Estate Management Intelligence — AI-powered property analytics and operations."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.settings = settings
    install_error_handlers(application)
    _attach_routers(application)
    _attach_health(application)
    application.add_middleware(RequestIDMiddleware)
    _add_cors(application, settings)
    return application


def _attach_health(application: FastAPI) -> None:
    """Add ``/health`` endpoint for live assessment."""
    import time as _time

    _boot_time = _time.time()

    @application.get("/health", tags=["ops"])
    async def health() -> dict[str, Any]:
        container = getattr(application.state, "container", None)
        trace_count = 0
        if container is not None:
            traces = await container.trace_store.list_traces(limit=1000)
            trace_count = len(traces)
        uptime_s = round(_time.time() - _boot_time)

        llm_calls = 0
        llm_cost_usd = 0.0
        llm_total_tokens = 0
        if container is not None and hasattr(container, "usage_ledger"):
            usage = container.usage_ledger.summary()
            llm_calls = usage.total_calls
            llm_cost_usd = round(usage.total_estimated_cost_usd, 6)
            llm_total_tokens = usage.total_tokens

        return {
            "status": "ok",
            "version": application.version,
            "uptime_s": uptime_s,
            "traces": trace_count,
            "llm_calls": llm_calls,
            "llm_total_tokens": llm_total_tokens,
            "llm_cost_usd": llm_cost_usd,
        }


app = create_app()
