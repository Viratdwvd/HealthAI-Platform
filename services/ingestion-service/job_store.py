"""
Ingestion Service – Redis-backed Job Store
------------------------------------------
Replaces the naive in-memory dict with a persistent, TTL-aware Redis store.
Automatically expires jobs after 24 h so Redis doesn't grow forever.

Usage:
    store = JobStore(redis_url="redis://redis:6379/0")
    await store.save(job)
    job = await store.get(job_id)
    jobs = await store.list(tenant_id)
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional
from uuid import UUID

import redis.asyncio as aioredis

import sys
sys.path.insert(0, "/app/shared")
from models.schemas import IngestionJob, JobStatus

_JOB_TTL_S = 86_400          # 24 hours
_KEY_PREFIX = "ingestion:job:"
_TENANT_SET = "ingestion:tenant:{tenant_id}:jobs"


class JobStore:
    def __init__(self, redis_url: str) -> None:
        self._redis = aioredis.from_url(redis_url, decode_responses=True)

    # ── CRUD ──────────────────────────────────────────────────────────────────

    async def save(self, job: IngestionJob) -> None:
        """Upsert a job. Also maintains a per-tenant set for listing."""
        key     = _KEY_PREFIX + str(job.job_id)
        payload = job.model_dump_json()

        pipe = self._redis.pipeline()
        pipe.set(key, payload, ex=_JOB_TTL_S)
        pipe.sadd(_TENANT_SET.format(tenant_id=job.tenant_id), str(job.job_id))
        pipe.expire(_TENANT_SET.format(tenant_id=job.tenant_id), _JOB_TTL_S)
        await pipe.execute()

    async def get(self, job_id: str) -> Optional[IngestionJob]:
        raw = await self._redis.get(_KEY_PREFIX + job_id)
        if not raw:
            return None
        return IngestionJob.model_validate_json(raw)

    async def list(self, tenant_id: str) -> List[IngestionJob]:
        """Return all jobs for a tenant (most-recent first)."""
        ids = await self._redis.smembers(_TENANT_SET.format(tenant_id=tenant_id))
        if not ids:
            return []

        keys    = [_KEY_PREFIX + jid for jid in ids]
        raws    = await self._redis.mget(*keys)
        jobs    = [IngestionJob.model_validate_json(r) for r in raws if r]
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)

    async def update_status(
        self,
        job_id: str,
        status: JobStatus,
        chunks: int = 0,
        error:  str | None = None,
    ) -> Optional[IngestionJob]:
        job = await self.get(job_id)
        if not job:
            return None
        job.status     = status
        job.chunks     = chunks
        job.error      = error
        job.updated_at = datetime.utcnow()
        await self.save(job)
        return job

    async def delete(self, job_id: str) -> bool:
        deleted = await self._redis.delete(_KEY_PREFIX + job_id)
        return bool(deleted)

    # ── Aggregates ────────────────────────────────────────────────────────────

    async def count_by_status(self, tenant_id: str) -> dict[str, int]:
        jobs   = await self.list(tenant_id)
        counts: dict[str, int] = {}
        for job in jobs:
            counts[job.status.value] = counts.get(job.status.value, 0) + 1
        return counts

    async def close(self) -> None:
        await self._redis.aclose()
