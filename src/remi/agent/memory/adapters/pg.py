"""Postgres-backed MemoryStore — durable agent memory that survives restarts."""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlmodel import col, select

from remi.agent.db.tables import MemoryEntryRow
from remi.agent.memory.store import MemoryStore
from remi.agent.memory.types import IMPORTANCE_TTL, Importance, MemoryEntry

_log = structlog.get_logger(__name__)


class PostgresMemoryStore(MemoryStore):
    """SQL-backed memory that survives server restarts."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def write(
        self,
        namespace: str,
        key: str,
        value: str,
        *,
        importance: int = Importance.ROUTINE,
        entity_ids: list[str] | None = None,
        tags: list[str] | None = None,
        source: str = "",
        ttl: int | None = None,
    ) -> None:
        if ttl is None:
            imp = Importance(min(importance, Importance.CRITICAL))
            ttl = IMPORTANCE_TTL.get(imp)
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
                existing.importance = importance
                existing.ttl_seconds = ttl
                existing.updated_at = now
                session.add(existing)
            else:
                row = MemoryEntryRow(
                    namespace=namespace,
                    key=key,
                    value=value,
                    importance=importance,
                    ttl_seconds=ttl,
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
            await session.commit()

    async def read(
        self,
        namespace: str,
        query: str,
        *,
        entity_ids: list[str] | None = None,
        tags: list[str] | None = None,
        limit: int = 10,
    ) -> list[MemoryEntry]:
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
            if (
                query_lower
                and query_lower not in row.key.lower()
                and query_lower not in row.value.lower()
            ):
                continue
            matches.append(
                MemoryEntry(
                    namespace=row.namespace,
                    key=row.key,
                    value=row.value,
                    importance=getattr(row, "importance", Importance.ROUTINE),
                    created_at=row.created_at,
                )
            )
        matches.sort(
            key=lambda e: (e.importance, (e.created_at or datetime.min).timestamp()), reverse=True
        )
        return matches[:limit]

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

    async def list_keys(self, namespace: str) -> list[str]:
        async with self._session_factory() as session:
            stmt = select(MemoryEntryRow.key).where(
                col(MemoryEntryRow.namespace) == namespace,
            )
            result = await session.exec(stmt)
            return list(result.all())

    async def delete(self, namespace: str, key: str) -> bool:
        async with self._session_factory() as session:
            stmt = select(MemoryEntryRow).where(
                col(MemoryEntryRow.namespace) == namespace,
                col(MemoryEntryRow.key) == key,
            )
            result = await session.exec(stmt)
            row = result.first()
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
            return True

    @staticmethod
    def _is_expired(row: MemoryEntryRow) -> bool:
        if row.ttl_seconds is None:
            return False
        age = (datetime.now(UTC) - row.updated_at).total_seconds()
        return age > row.ttl_seconds
