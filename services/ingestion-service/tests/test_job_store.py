"""
Unit tests – JobStore (Redis-backed)
Tests use fakeredis to avoid needing a real Redis instance.

Run with:
    PYTHONPATH=shared:services/ingestion-service pytest services/ingestion-service/tests/test_job_store.py -v
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import datetime

sys.path.insert(0, "shared")
sys.path.insert(0, "services/ingestion-service")

import pytest
import fakeredis.aioredis as fakeredis

from models.schemas import FileType, IngestionJob, JobStatus
from job_store import JobStore


@pytest.fixture
async def store():
    """JobStore backed by fakeredis (no real Redis needed)."""
    fake_redis = await fakeredis.FakeRedis.create(decode_responses=True)
    s = JobStore.__new__(JobStore)
    s._redis = fake_redis
    yield s
    await fake_redis.aclose()


def _make_job(tenant_id: str = "t1") -> IngestionJob:
    return IngestionJob(
        tenant_id=tenant_id,
        user_id="user1",
        file_name="test.csv",
        file_type=FileType.CSV,
    )


@pytest.mark.asyncio
async def test_save_and_get(store):
    job = _make_job()
    await store.save(job)
    retrieved = await store.get(str(job.job_id))
    assert retrieved is not None
    assert retrieved.job_id == job.job_id
    assert retrieved.tenant_id == "t1"


@pytest.mark.asyncio
async def test_get_missing_returns_none(store):
    result = await store.get(str(uuid.uuid4()))
    assert result is None


@pytest.mark.asyncio
async def test_update_status_done(store):
    job = _make_job()
    await store.save(job)
    updated = await store.update_status(str(job.job_id), JobStatus.DONE, chunks=42)
    assert updated is not None
    assert updated.status == JobStatus.DONE
    assert updated.chunks == 42
    # Verify persisted
    reloaded = await store.get(str(job.job_id))
    assert reloaded.status == JobStatus.DONE
    assert reloaded.chunks == 42


@pytest.mark.asyncio
async def test_update_status_failed(store):
    job = _make_job()
    await store.save(job)
    updated = await store.update_status(str(job.job_id), JobStatus.FAILED, error="Parse error")
    assert updated.status  == JobStatus.FAILED
    assert updated.error   == "Parse error"


@pytest.mark.asyncio
async def test_update_status_missing_job(store):
    result = await store.update_status(str(uuid.uuid4()), JobStatus.DONE)
    assert result is None


@pytest.mark.asyncio
async def test_list_returns_tenant_jobs(store):
    job_a = _make_job("tenant-a")
    job_b = _make_job("tenant-a")
    job_c = _make_job("tenant-b")
    for j in (job_a, job_b, job_c):
        await store.save(j)

    jobs_a = await store.list("tenant-a")
    jobs_b = await store.list("tenant-b")

    assert len(jobs_a) == 2
    assert len(jobs_b) == 1
    assert all(j.tenant_id == "tenant-a" for j in jobs_a)
    assert jobs_b[0].tenant_id == "tenant-b"


@pytest.mark.asyncio
async def test_list_empty_tenant(store):
    jobs = await store.list("nobody")
    assert jobs == []


@pytest.mark.asyncio
async def test_delete_job(store):
    job = _make_job()
    await store.save(job)
    deleted = await store.delete(str(job.job_id))
    assert deleted is True
    assert await store.get(str(job.job_id)) is None


@pytest.mark.asyncio
async def test_delete_missing_job(store):
    deleted = await store.delete(str(uuid.uuid4()))
    assert deleted is False


@pytest.mark.asyncio
async def test_count_by_status(store):
    jobs = [_make_job("tenant-x") for _ in range(5)]
    for j in jobs:
        await store.save(j)
    # Update 2 to done, 1 to failed, leave 2 pending
    await store.update_status(str(jobs[0].job_id), JobStatus.DONE, chunks=10)
    await store.update_status(str(jobs[1].job_id), JobStatus.DONE, chunks=20)
    await store.update_status(str(jobs[2].job_id), JobStatus.FAILED, error="err")

    counts = await store.count_by_status("tenant-x")
    assert counts["done"]    == 2
    assert counts["failed"]  == 1
    assert counts["pending"] == 2
