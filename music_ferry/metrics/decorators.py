# music_ferry/metrics/decorators.py
"""Decorators for timing operations with Prometheus metrics."""

import functools
import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

from music_ferry.metrics.collectors import sync_duration_seconds

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def timed_sync(source: str) -> Callable[[F], F]:
    """Decorator to time sync operations and record to Prometheus histogram.

    Args:
        source: The source being synced (e.g., "spotify", "youtube").

    Example:
        @timed_sync("spotify")
        async def sync_spotify_playlist(...):
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start_time
                sync_duration_seconds.labels(source=source).observe(duration)
                logger.debug(f"Sync {source} completed in {duration:.2f}s")

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start_time
                sync_duration_seconds.labels(source=source).observe(duration)
                logger.debug(f"Sync {source} completed in {duration:.2f}s")

        # Return appropriate wrapper based on function type
        if asyncio_iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


def asyncio_iscoroutinefunction(func: Callable[..., Any]) -> bool:
    """Check if a function is a coroutine function."""
    import asyncio
    import inspect

    return asyncio.iscoroutinefunction(func) or inspect.iscoroutinefunction(func)
