"""Database layer — async SQLModel/SQLAlchemy engine and session management.

Agent-layer table definitions live in ``agent.db.tables``.
Application-domain tables live in ``application.infra.stores.pg.tables``.

Public API::

    from remi.agent.db import create_tables
"""

from remi.agent.db.engine import create_tables

__all__ = [
    "create_tables",
]
