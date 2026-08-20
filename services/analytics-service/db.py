"""
Analytics Service – Async SQLAlchemy DB Layer
---------------------------------------------
Provides:
  • get_db()           – FastAPI dependency that yields an AsyncSession
  • DatasetRecord      – ORM model for dataset metadata
  • AnalyticsCacheRecord – ORM model for result caching
  • DatasetRepository  – CRUD methods for datasets
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, Dict, List, Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer,
    String, Text, select, delete,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

import sys
sys.path.insert(0, "/app/shared")
from config.settings import AnalyticsSettings

_settings = AnalyticsSettings()

# ─── Engine ───────────────────────────────────────────────────────────────────

_engine = create_async_engine(
    _settings.POSTGRES_DSN,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

_SessionFactory = async_sessionmaker(
    _engine, expire_on_commit=False, class_=AsyncSession
)


# ─── FastAPI dependency ───────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with _SessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ─── ORM models ───────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


class DatasetRecord(Base):
    __tablename__ = "datasets"

    dataset_id:  str      = Column(UUID(as_uuid=False), primary_key=True)
    tenant_id:   str      = Column(String, nullable=False, index=True)
    name:        str      = Column(String, nullable=False)
    description: str      = Column(Text)
    row_count:   int      = Column(Integer, default=0)
    schema_json: dict     = Column(JSONB)
    created_at:  datetime = Column(DateTime, default=datetime.utcnow)


class AnalyticsCacheRecord(Base):
    __tablename__ = "analytics_cache"

    cache_key:   str      = Column(String, primary_key=True)
    tenant_id:   str      = Column(String, nullable=False)
    operation:   str      = Column(String, nullable=False)
    result_json: dict     = Column(JSONB, nullable=False)
    created_at:  datetime = Column(DateTime, default=datetime.utcnow)
    expires_at:  datetime = Column(DateTime, nullable=False)


class QueryAuditRecord(Base):
    __tablename__ = "query_audit"

    id:          int      = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id:   str      = Column(String, nullable=False, index=True)
    user_id:     str      = Column(String, nullable=False)
    session_id:  str      = Column(String, index=True)
    query_text:  str      = Column(Text, nullable=False)
    intent:      str      = Column(String)
    answer_len:  int      = Column(Integer)
    confidence:  float    = Column(Float)
    latency_ms:  float    = Column(Float)
    sources:     dict     = Column(JSONB, default=list)
    created_at:  datetime = Column(DateTime, default=datetime.utcnow, index=True)


# ─── Repository ───────────────────────────────────────────────────────────────

class DatasetRepository:
    """Encapsulates all dataset DB operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, tenant_id: str, dataset_id: str) -> Optional[DatasetRecord]:
        result = await self._session.execute(
            select(DatasetRecord).where(
                DatasetRecord.tenant_id == tenant_id,
                DatasetRecord.dataset_id == dataset_id,
            )
        )
        return result.scalar_one_or_none()

    async def list(self, tenant_id: str) -> List[DatasetRecord]:
        result = await self._session.execute(
            select(DatasetRecord)
            .where(DatasetRecord.tenant_id == tenant_id)
            .order_by(DatasetRecord.created_at.desc())
        )
        return list(result.scalars().all())

    async def upsert(self, record: DatasetRecord) -> DatasetRecord:
        self._session.add(record)
        await self._session.flush()
        return record

    async def delete(self, tenant_id: str, dataset_id: str) -> bool:
        result = await self._session.execute(
            delete(DatasetRecord).where(
                DatasetRecord.tenant_id == tenant_id,
                DatasetRecord.dataset_id == dataset_id,
            )
        )
        return result.rowcount > 0


class AnalyticsCacheRepository:
    """Read-through/write-through cache for analytics results."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        result = await self._session.execute(
            select(AnalyticsCacheRecord).where(
                AnalyticsCacheRecord.cache_key == cache_key,
                AnalyticsCacheRecord.expires_at > datetime.utcnow(),
            )
        )
        row = result.scalar_one_or_none()
        return row.result_json if row else None

    async def set(
        self,
        cache_key:  str,
        tenant_id:  str,
        operation:  str,
        result:     Dict[str, Any],
        ttl_s:      int = 3600,
    ) -> None:
        record = AnalyticsCacheRecord(
            cache_key=cache_key,
            tenant_id=tenant_id,
            operation=operation,
            result_json=result,
            expires_at=datetime.utcnow() + timedelta(seconds=ttl_s),
        )
        await self._session.merge(record)
        await self._session.flush()

    async def purge_expired(self) -> int:
        result = await self._session.execute(
            delete(AnalyticsCacheRecord).where(
                AnalyticsCacheRecord.expires_at <= datetime.utcnow()
            )
        )
        return result.rowcount


class QueryAuditRepository:
    """Append-only audit log for queries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def log(
        self,
        tenant_id:   str,
        user_id:     str,
        query_text:  str,
        answer_len:  int,
        confidence:  float,
        latency_ms:  float,
        intent:      str       = "",
        session_id:  str | None = None,
        sources:     list      = (),
    ) -> None:
        record = QueryAuditRecord(
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            query_text=query_text,
            intent=intent,
            answer_len=answer_len,
            confidence=confidence,
            latency_ms=latency_ms,
            sources=list(sources),
        )
        self._session.add(record)
        await self._session.flush()

    async def recent(
        self, tenant_id: str, limit: int = 50
    ) -> List[QueryAuditRecord]:
        result = await self._session.execute(
            select(QueryAuditRecord)
            .where(QueryAuditRecord.tenant_id == tenant_id)
            .order_by(QueryAuditRecord.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
