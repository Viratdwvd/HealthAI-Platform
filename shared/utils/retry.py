"""
Retry and circuit-breaker helpers.
Import where you need resilient HTTP calls beyond what tenacity provides.

Usage:
    from utils.retry import with_retry, CircuitBreaker

    @with_retry(max_attempts=3, backoff_base=1.5)
    async def call_external_api(): ...

    breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30)
    async with breaker:
        await call_external_api()
"""

from __future__ import annotations

import asyncio
import functools
import time
from enum import Enum
from typing import Any, Callable, Coroutine, Type, Tuple

from utils.logger import get_logger

log = get_logger(__name__)


# ─── Retry decorator ──────────────────────────────────────────────────────────

def with_retry(
    max_attempts:  int   = 3,
    backoff_base:  float = 2.0,
    backoff_max:   float = 30.0,
    retriable:     Tuple[Type[Exception], ...] = (Exception,),
) -> Callable:
    """
    Async decorator that retries on the specified exception types with
    exponential back-off.

    Example:
        @with_retry(max_attempts=4, retriable=(httpx.RequestError,))
        async def fetch(url: str): ...
    """
    def decorator(fn: Callable[..., Coroutine]) -> Callable:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            delay = 1.0
            last_exc: Exception | None = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await fn(*args, **kwargs)
                except retriable as exc:
                    last_exc = exc
                    if attempt == max_attempts:
                        break
                    sleep_s = min(delay, backoff_max)
                    log.warning(
                        "retry_scheduled",
                        fn=fn.__name__,
                        attempt=attempt,
                        max=max_attempts,
                        sleep_s=round(sleep_s, 2),
                        error=str(exc),
                    )
                    await asyncio.sleep(sleep_s)
                    delay *= backoff_base

            log.error("retry_exhausted", fn=fn.__name__, attempts=max_attempts, error=str(last_exc))
            raise last_exc  # type: ignore

        return wrapper
    return decorator


# ─── Circuit breaker ──────────────────────────────────────────────────────────

class _State(Enum):
    CLOSED   = "closed"    # normal operation
    OPEN     = "open"      # blocking calls
    HALF_OPEN = "half_open" # probe call allowed


class CircuitBreaker:
    """
    Simple in-process circuit breaker.

    States:
      CLOSED   → calls pass through; failures are counted
      OPEN     → calls are rejected immediately; waits recovery_timeout
      HALF_OPEN → one probe call is allowed; success → CLOSED, failure → OPEN

    Usage (async context manager):
        breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30)
        try:
            async with breaker:
                result = await risky_call()
        except CircuitOpenError:
            result = fallback_value()
    """

    def __init__(
        self,
        failure_threshold:  int   = 5,
        recovery_timeout:   float = 30.0,
        success_threshold:  int   = 2,
    ) -> None:
        self._threshold  = failure_threshold
        self._timeout    = recovery_timeout
        self._successes_needed = success_threshold

        self._state:          _State = _State.CLOSED
        self._failure_count:  int    = 0
        self._success_count:  int    = 0
        self._opened_at:      float  = 0.0

    # ── async context manager ──────────────────────────────────────────────────

    async def __aenter__(self) -> "CircuitBreaker":
        self._check()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is not None:
            self._on_failure()
            return False   # do not suppress
        self._on_success()
        return False

    # ── internals ─────────────────────────────────────────────────────────────

    def _check(self) -> None:
        if self._state == _State.OPEN:
            if time.monotonic() - self._opened_at >= self._timeout:
                log.info("circuit_half_open")
                self._state = _State.HALF_OPEN
            else:
                raise CircuitOpenError(
                    f"Circuit is OPEN; retry after "
                    f"{self._timeout - (time.monotonic() - self._opened_at):.1f}s"
                )

    def _on_success(self) -> None:
        if self._state == _State.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self._successes_needed:
                log.info("circuit_closed")
                self._reset()
        elif self._state == _State.CLOSED:
            self._failure_count = 0

    def _on_failure(self) -> None:
        self._failure_count += 1
        if self._state == _State.HALF_OPEN or self._failure_count >= self._threshold:
            log.warning("circuit_opened", failures=self._failure_count)
            self._state     = _State.OPEN
            self._opened_at = time.monotonic()
            self._failure_count = 0
            self._success_count = 0

    def _reset(self) -> None:
        self._state         = _State.CLOSED
        self._failure_count = 0
        self._success_count = 0

    @property
    def state(self) -> str:
        return self._state.value


class CircuitOpenError(RuntimeError):
    """Raised when a call is blocked by an open circuit breaker."""
