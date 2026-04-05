"""Config package — DI container and settings.

Public API::

    from remi.shell.config import Container, RemiSettings
"""

from remi.shell.config.container import Container
from remi.shell.config.settings import RemiSettings

__all__ = [
    "Container",
    "RemiSettings",
]
