"""
Sliding-window rate limiter backed by Redis.
Returns (allowed: bool, retry_after_seconds: int).
"""

from __future__ import annotations
import time
from typing import Tuple

import redis.asyncio as aioredis


class RateLimiter:
    def __init__(self, redis_url: str, max_per_minute: int = 60) -> None:
        self._redis   = aioredis.from_url(redis_url, decode_responses=True)
        self._max     = max_per_minute
        self._window  = 60          # seconds

    async def check(self, client_id: str) -> Tuple[bool, int]:
        """
        Returns (True, 0)        if request is allowed.
        Returns (False, seconds) if limit exceeded.
        """
        key = f"rl:{client_id}"
        now = int(time.time())
        pipe = self._redis.pipeline()
        pipe.zadd(key, {str(now): now})                       # add current timestamp
        pipe.zremrangebyscore(key, 0, now - self._window)     # prune old entries
        pipe.zcard(key)                                        # count in window
        pipe.expire(key, self._window)
        results = await pipe.execute()
        count: int = results[2]
        if count > self._max:
            oldest = await self._redis.zrange(key, 0, 0, withscores=True)
            retry_after = self._window - (now - int(oldest[0][1])) if oldest else self._window
            return False, max(1, retry_after)
        return True, 0
