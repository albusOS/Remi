"""FastAPI dependency injection for application routes.

Provides the ``Ctr`` type alias that all ``application/*.api`` route
handlers use to access the DI container.  This module has **zero imports
from ``shell/``** — it relies on FastAPI's ``request.app.state`` to
retrieve whatever container the shell placed there at startup.

This breaks the circular dependency that previously existed:
``application.api → shell.api.dependencies → shell.config.container
→ application`` (cycle).  Now the arrow is simply
``application.api → application.dependencies`` (inner-ring only).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, Request


def get_container(request: Request) -> Any:
    """Pull the DI container off ``request.app.state``.

    Override this via ``app.dependency_overrides`` in tests.
    """
    return request.app.state.container


Ctr = Annotated[Any, Depends(get_container)]
