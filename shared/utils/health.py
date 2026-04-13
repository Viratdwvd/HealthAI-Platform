"""
shared/utils/health.py
----------------------
Common health-check helper used by every FastAPI service.

Usage:
    from utils.health import HealthChecker, DependencyCheck

    checker = HealthChecker("my-service", version="1.0.0")
    checker.add(DependencyCheck("redis",  _ping_redis))
    checker.add(DependencyCheck("kafka",  _ping_kafka))

    @app.get("/health")
    async def health():
        return await checker.run()
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional

from models.schemas import HealthResponse


# ─── Dependency probe ─────────────────────────────────────────────────────────

@dataclass
class DependencyCheck:
    name:    str
    probe:   Callable[[], Coroutine[Any, Any, bool]]
    timeout: float = 3.0          # seconds


# ─── Checker ──────────────────────────────────────────────────────────────────

class HealthChecker:
    """
    Runs multiple async dependency probes in parallel and aggregates results.

    The /health route returns:
      • status="ok"       – all probes passed
      • status="degraded" – some probes failed (service still running)
    """

    def __init__(self, service_name: str, version: str = "1.0.0") -> None:
        self._service  = service_name
        self._version  = version
        self._checks:  List[DependencyCheck] = []
        self._started: float = time.monotonic()

    def add(self, check: DependencyCheck) -> "HealthChecker":
        self._checks.append(check)
        return self

    async def run(self) -> HealthResponse:
        details: Dict[str, Any] = {
            "uptime_s": round(time.monotonic() - self._started, 1),
        }

        if self._checks:
            tasks = [
                asyncio.wait_for(self._run_one(c), timeout=c.timeout)
                for c in self._checks
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for check, result in zip(self._checks, results):
                if isinstance(result, Exception):
                    details[check.name] = f"error: {result}"
                else:
                    details[check.name] = "ok" if result else "degraded"

        overall = "ok" if all(
            v in ("ok", True) for k, v in details.items() if k != "uptime_s"
        ) else "degraded"

        return HealthResponse(
            service=self._service,
            status=overall,
            version=self._version,
            details=details,
        )

    @staticmethod
    async def _run_one(check: DependencyCheck) -> bool:
        try:
            return await check.probe()
        except Exception:
            return False


# ─── Built-in probes ──────────────────────────────────────────────────────────

def redis_probe(redis_url: str) -> Callable[[], Coroutine]:
    """Returns an async probe function that pings Redis."""
    async def _probe() -> bool:
        import redis.asyncio as aioredis
        r = aioredis.from_url(redis_url)
        result = await r.ping()
        await r.aclose()
        return result is True
    return _probe


def kafka_probe(bootstrap_servers: str) -> Callable[[], Coroutine]:
    """Returns an async probe that checks if Kafka brokers are reachable."""
    async def _probe() -> bool:
        from aiokafka import AIOKafkaProducer
        producer = AIOKafkaProducer(bootstrap_servers=bootstrap_servers)
        try:
            await producer.start()
            return True
        finally:
            await producer.stop()
    return _probe


def http_probe(url: str) -> Callable[[], Coroutine]:
    """Returns an async probe that GETs a URL and checks for 200."""
    async def _probe() -> bool:
        import httpx
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(url)
            return r.status_code == 200
    return _probe


def qdrant_probe(qdrant_url: str) -> Callable[[], Coroutine]:
    """Returns an async probe that checks Qdrant readiness."""
    async def _probe() -> bool:
        import httpx
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{qdrant_url}/readyz")
            return r.status_code == 200
    return _probe
