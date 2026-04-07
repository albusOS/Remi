"""Config package — settings and capability registration.

Import ``Container`` directly from ``remi.shell.config.container`` —
it is not re-exported here to avoid triggering the full dependency
chain on any import of ``remi.shell.config``.

Public API::

    from remi.shell.config.container import Container
    from remi.shell.config.settings import RemiSettings
"""

from remi.shell.config.settings import RemiSettings

__all__ = [
    "RemiSettings",
]
