"""Database layer — async SQLModel/SQLAlchemy engine, tables, and session management.

Public API::

    from remi.agent.db import create_tables
"""

from remi.agent.db.engine import create_tables

__all__ = [
    "create_tables",
]
