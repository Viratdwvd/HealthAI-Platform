"""
Unit tests – LLM Response Cache
Run with:
    PYTHONPATH=shared:services/llm-service pytest services/llm-service/tests/test_cache.py -v
"""

from __future__ import annotations
import asyncio
import sys
sys.path.insert(0, "shared")
sys.path.insert(0, "services/llm-service")

import pytest
import fakeredis.aioredis as fakeredis
from cache.response_cache import LLMCache


@pytest.fixture
async def cache():
    """LLMCache backed by fakeredis."""
    c = LLMCache.__new__(LLMCache)
    c._url         = "redis://fake"
    c._default_ttl = 300
    c._max_size    = 1000
    c._redis       = await fakeredis.FakeRedis.create(decode_responses=True)
    yield c
    await c._redis.aclose()


@pytest.mark.asyncio
async def test_cache_miss_returns_none(cache):
    result = await cache.get("nonexistent-key")
    assert result is None


@pytest.mark.asyncio
async def test_cache_set_and_get(cache):
    value = {"content": "Patient has hypertension.", "model": "gpt-4o", "tokens_in": 100}
    await cache.set("test-key-1", value)
    result = await cache.get("test-key-1")
    assert result == value


@pytest.mark.asyncio
async def test_cache_make_key_deterministic(cache):
    k1 = LLMCache.make_key("sys", "user prompt", "gpt-4o", temperature=0.0)
    k2 = LLMCache.make_key("sys", "user prompt", "gpt-4o", temperature=0.0)
    assert k1 == k2


@pytest.mark.asyncio
async def test_cache_make_key_different_prompts(cache):
    k1 = LLMCache.make_key("sys", "prompt A", "gpt-4o")
    k2 = LLMCache.make_key("sys", "prompt B", "gpt-4o")
    assert k1 != k2


@pytest.mark.asyncio
async def test_cache_make_key_different_models(cache):
    k1 = LLMCache.make_key("sys", "prompt", "gpt-4o")
    k2 = LLMCache.make_key("sys", "prompt", "gpt-4-turbo")
    assert k1 != k2


@pytest.mark.asyncio
async def test_cache_delete(cache):
    await cache.set("del-key", {"content": "test"})
    await cache.delete("del-key")
    result = await cache.get("del-key")
    assert result is None


@pytest.mark.asyncio
async def test_cache_stats_tracks_hits_misses(cache):
    await cache.set("sk1", {"content": "a"})
    await cache.set("sk2", {"content": "b"})

    await cache.get("sk1")       # hit
    await cache.get("sk2")       # hit
    await cache.get("sk3")       # miss
    await cache.get("sk4")       # miss
    await cache.get("sk5")       # miss

    stats = await cache.stats()
    assert stats.hits   == 2
    assert stats.misses == 3
    assert stats.total  == 5
    assert abs(stats.hit_rate - 0.4) < 0.001


@pytest.mark.asyncio
async def test_cache_flush_pattern(cache):
    await cache.set("llm:resp:aaa", {"content": "a"})
    await cache.set("llm:resp:bbb", {"content": "b"})
    await cache.set("other:key",    {"content": "c"})

    deleted = await cache.flush_pattern("llm:resp:*")
    assert deleted == 2

    assert await cache.get("llm:resp:aaa") is None
    assert await cache.get("llm:resp:bbb") is None


@pytest.mark.asyncio
async def test_cache_warm(cache):
    entries = [
        (LLMCache.make_key("sys", f"q{i}", "gpt-4o"), {"content": f"answer {i}"})
        for i in range(5)
    ]
    count = await cache.warm(entries)
    assert count == 5

    for key, val in entries:
        cached = await cache.get(key)
        assert cached == val


@pytest.mark.asyncio
async def test_cache_returns_none_without_redis():
    c = LLMCache.__new__(LLMCache)
    c._redis = None
    result = await c.get("anything")
    assert result is None
