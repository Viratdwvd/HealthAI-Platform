from __future__ import annotations
import logging
import sys
import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Generator, Optional

import structlog

def configure_logging(service_name: str, log_level: str = "INFO") -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(log_level)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

def get_logger(name: str) -> structlog.BoundLogger:
    return structlog.get_logger(name)

@contextmanager
def timer(label: str, log: Optional[Any] = None) -> Generator[None, None, None]:
    t0 = time.perf_counter()
    yield
    elapsed = (time.perf_counter() - t0) * 1000
    msg = f"{label} took {elapsed:.1f}ms"
    if log:
        log.info(msg)
    else:
        print(msg)

def timed(fn: Callable) -> Callable:
    log = get_logger(fn.__module__)
    @wraps(fn)
    async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        t0 = time.perf_counter()
        result = await fn(*args, **kwargs)
        log.info("call_latency", fn=fn.__name__, ms=round((time.perf_counter() - t0) * 1000, 1))
        return result
    @wraps(fn)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        t0 = time.perf_counter()
        result = fn(*args, **kwargs)
        log.info("call_latency", fn=fn.__name__, ms=round((time.perf_counter() - t0) * 1000, 1))
        return result
    import asyncio
    return async_wrapper if asyncio.iscoroutinefunction(fn) else sync_wrapper