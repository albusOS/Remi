"""Postgres-backed MemoryStore — durable episodic memory for agents."""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlmodel import col, select

from remi.agent.db.tables import MemoryEntryRow
from remi.agent.graph.stores import MemoryStore
from remi.agent.graph.types import MemoryEntry

_log = structlog.get_logger(__name__)


class PostgresMemoryStore(MemoryStore):
    """SQL-backed key-value memory that survives server restarts."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def store(self, namespace: str, key: str, value: str, *, ttl: int | None = None) -> None:
        now = datetime.now(UTC)
        async with self._session_factory() as session:
            stmt = select(MemoryEntryRow).where(
                col(MemoryEntryRow.namespace) == namespace,
                col(MemoryEntryRow.key) == key,
            )
            result = await session.exec(stmt)
            existing = result.first()

            if existing is not None:
                existing.value = value
                existing.ttl_seconds = ttl
                existing.updated_at = now
                session.add(existing)
            else:
                row = MemoryEntryRow(
                    namespace=namespace,
                    key=key,
                    value=value,
                    ttl_seconds=ttl,
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
            await session.commit()

    async def recall(self, namespace: str, key: str) -> str | None:
        async with self._session_factory() as session:
            stmt = select(MemoryEntryRow).where(
                col(MemoryEntryRow.namespace) == namespace,
                col(MemoryEntryRow.key) == key,
            )
            result = await session.exec(stmt)
            row = result.first()
            if row is None:
                return None
            if self._is_expired(row):
                await session.delete(row)
                await session.commit()
                return None
            return row.value

    async def search(self, namespace: str, query: str, *, limit: int = 5) -> list[MemoryEntry]:
        query_lower = query.lower()
        async with self._session_factory() as session:
            stmt = select(MemoryEntryRow).where(
                col(MemoryEntryRow.namespace) == namespace,
            )
            result = await session.exec(stmt)
            rows = result.all()

        matches: list[MemoryEntry] = []
        for row in rows:
            if self._is_expired(row):
                continue
            if query_lower in row.key.lower() or query_lower in row.value.lower():
                matches.append(
                    MemoryEntry(
                        namespace=row.namespace,
                        key=row.key,
                        value=row.value,
                        created_at=row.created_at,
                    )
                )
                if len(matches) >= limit:
                    break
        return matches

    async def list_keys(self, namespace: str) -> list[str]:
        async with self._session_factory() as session:
            stmt = select(MemoryEntryRow.key).where(
                col(MemoryEntryRow.namespace) == namespace,
            )
            result = await session.exec(stmt)
            keys = list(result.all())
        return keys

    @staticmethod
    def _is_expired(row: MemoryEntryRow) -> bool:
        if row.ttl_seconds is None:
            return False
        age = (datetime.now(UTC) - row.updated_at).total_seconds()
        return age > row.ttl_seconds
