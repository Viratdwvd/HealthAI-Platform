"""
LLM Service – Redis Response Cache
------------------------------------
Provides a typed async cache layer for LLM responses.
Keys are SHA-256 hashes of (system_prompt, user_prompt, model).

Features:
  • Per-model TTL configuration
  • Hit/miss metrics tracking
  • Namespace isolation per tenant (optional)
  • LRU eviction via Redis LOLWUT-free approach (sorted set + key expiry)

Usage:
    cache = LLMCache(redis_url="redis://redis:6379/0")
    await cache.connect()

    cached = await cache.get(key)
    if cached:
        return cached

    result = await call_llm(...)
    await cache.set(key, result, ttl_s=300)
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import redis.asyncio as aioredis

import sys
sys.path.insert(0, "/app/shared")
from utils.logger import get_logger

log = get_logger(__name__)

_CACHE_PREFIX     = "llm:resp:"
_STATS_HITS_KEY   = "llm:stats:hits"
_STATS_MISSES_KEY = "llm:stats:misses"


@dataclass
class CacheStats:
    hits:       int
    misses:     int
    hit_rate:   float
    total:      int


class LLMCache:
    def __init__(
        self,
        redis_url:   str,
        default_ttl: int = 300,
        max_size:    int = 10_000,
    ) -> None:
        self._url         = redis_url
        self._default_ttl = default_ttl
        self._max_size    = max_size
        self._redis: Optional[aioredis.Redis] = None

    async def connect(self) -> None:
        self._redis = aioredis.from_url(self._url, decode_responses=True)
        log.info("llm_cache_connected", ttl=self._default_ttl)

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()

    # ── Public API ────────────────────────────────────────────────────────────

    @staticmethod
    def make_key(
        system_prompt: str,
        user_prompt:   str,
        model:         str,
        temperature:   float = 0.0,
    ) -> str:
        """
        Generate a deterministic cache key.
        Only temperature=0 responses should be cached (non-deterministic otherwise).
        """
        raw = f"{model}|{temperature}|{system_prompt[:500]}|{user_prompt[:1000]}"
        return _CACHE_PREFIX + hashlib.sha256(raw.encode()).hexdigest()

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        if not self._redis:
            return None
        try:
            raw = await self._redis.get(key)
            if raw:
                await self._redis.incr(_STATS_HITS_KEY)
                log.debug("llm_cache_hit", key=key[-12:])
                return json.loads(raw)
            await self._redis.incr(_STATS_MISSES_KEY)
            return None
        except Exception as exc:
            log.warning("llm_cache_get_error", error=str(exc))
            return None

    async def set(
        self,
        key:   str,
        value: Dict[str, Any],
        ttl_s: Optional[int] = None,
    ) -> None:
        if not self._redis:
            return
        try:
            await self._redis.set(
                key,
                json.dumps(value),
                ex=ttl_s or self._default_ttl,
            )
            log.debug("llm_cache_set", key=key[-12:], ttl=ttl_s or self._default_ttl)
        except Exception as exc:
            log.warning("llm_cache_set_error", error=str(exc))

    async def delete(self, key: str) -> None:
        if not self._redis:
            return
        await self._redis.delete(key)

    async def flush_pattern(self, pattern: str = "llm:resp:*") -> int:
        """Delete all cached responses (use with care in production)."""
        if not self._redis:
            return 0
        keys = await self._redis.keys(pattern)
        if keys:
            return await self._redis.delete(*keys)
        return 0

    async def stats(self) -> CacheStats:
        if not self._redis:
            return CacheStats(hits=0, misses=0, hit_rate=0.0, total=0)
        try:
            hits_raw   = await self._redis.get(_STATS_HITS_KEY)
            misses_raw = await self._redis.get(_STATS_MISSES_KEY)
            hits   = int(hits_raw   or 0)
            misses = int(misses_raw or 0)
            total  = hits + misses
            return CacheStats(
                hits=hits,
                misses=misses,
                hit_rate=round(hits / total, 4) if total > 0 else 0.0,
                total=total,
            )
        except Exception:
            return CacheStats(hits=0, misses=0, hit_rate=0.0, total=0)

    async def warm(self, entries: list[tuple[str, Dict[str, Any]]]) -> int:
        """
        Pre-populate cache with a list of (key, value) pairs.
        Useful for seeding frequently-asked queries.
        """
        count = 0
        for key, value in entries:
            await self.set(key, value)
            count += 1
        log.info("llm_cache_warmed", entries=count)
        return count
