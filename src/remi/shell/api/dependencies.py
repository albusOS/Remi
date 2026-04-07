"""FastAPI dependency injection — re-exports from application layer.

The canonical ``Ctr`` type alias and ``get_container`` function live in
``remi.application.dependencies``.  This module re-exports them so that
any shell-layer code (or tests) that imported from the old location
continues to work.

New code should import from ``remi.application.dependencies`` directly.
"""

from remi.application.dependencies import Ctr, get_container

__all__ = [
    "Ctr",
    "get_container",
]
