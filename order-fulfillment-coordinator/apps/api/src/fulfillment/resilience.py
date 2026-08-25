from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Callable, TypeVar
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerError(Exception):
    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: float = 30.0,
        excluded_exceptions: tuple[type[Exception], ...] = (),
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.excluded_exceptions = excluded_exceptions

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if self._last_failure_time and (time.time() - self._last_failure_time) >= self.timeout:
                return CircuitState.HALF_OPEN
        return self._state

    async def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        async with self._lock:
            current_state = self.state
            if current_state == CircuitState.OPEN:
                retry_after = self.timeout - (time.time() - (self._last_failure_time or 0))
                raise CircuitBreakerError(
                    f"Circuit breaker '{self.name}' is OPEN",
                    retry_after=max(0, retry_after)
                )

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            await self._on_success()
            return result

        except self.excluded_exceptions:
            raise
        except Exception:
            await self._on_failure()
            raise

    async def _on_success(self) -> None:
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    logger.info("Circuit breaker '%s' CLOSED after recovery", self.name)
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    async def _on_failure(self) -> None:
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._success_count = 0
                logger.warning("Circuit breaker '%s' reopened after half-open failure", self.name)
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.failure_threshold:
                    self._state = CircuitState.OPEN
                    logger.warning(
                        "Circuit breaker '%s' OPENED after %d failures",
                        self.name, self.failure_threshold
                    )


_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    success_threshold: int = 2,
    timeout: float = 30.0,
    excluded_exceptions: tuple[type[Exception], ...] = (),
) -> CircuitBreaker:
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold,
            success_threshold=success_threshold,
            timeout=timeout,
            excluded_exceptions=excluded_exceptions,
        )
    return _circuit_breakers[name]


async def with_retry(
    func: Callable[..., T],
    *args: Any,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retry_exceptions: tuple[type[Exception], ...] = (Exception,),
    on_retry: Callable[[Exception, int], None] | None = None,
    **kwargs: Any,
) -> T:
    last_exception: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    return await result
                return result
        except retry_exceptions as e:
            last_exception = e
            if attempt < max_retries:
                delay = min(base_delay * (exponential_base ** attempt), max_delay)
                if jitter:
                    import random
                    delay *= (0.5 + random.random())
                logger.warning(
                    "Retry %d/%d for %s after %.1fs: %s",
                    attempt + 1, max_retries, func.__name__, delay, e
                )
                if on_retry:
                    on_retry(e, attempt + 1)
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "All %d retries exhausted for %s: %s",
                    max_retries, func.__name__, last_exception
                )

    raise last_exception


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retry_exceptions: tuple[type[Exception], ...] = (Exception,),
):
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            return await with_retry(
                func, *args,
                max_retries=max_retries,
                base_delay=base_delay,
                max_delay=max_delay,
                exponential_base=exponential_base,
                jitter=jitter,
                retry_exceptions=retry_exceptions,
                **kwargs
            )

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            return asyncio.run(with_retry(
                func, *args,
                max_retries=max_retries,
                base_delay=base_delay,
                max_delay=max_delay,
                exponential_base=exponential_base,
                jitter=jitter,
                retry_exceptions=retry_exceptions,
                **kwargs
            ))

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


class RateLimiter:
    def __init__(self, max_calls: int, window_seconds: float):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self.calls: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.time()
            self.calls = [c for c in self.calls if now - c < self.window_seconds]
            if len(self.calls) >= self.max_calls:
                wait_time = self.calls[0] + self.window_seconds - now
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
            self.calls.append(time.time())


class Bulkhead:
    def __init__(self, max_concurrent: int):
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def execute(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        async with self.semaphore:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)


class TimeoutError(Exception):
    pass


async def with_timeout(
    func: Callable[..., T],
    *args: Any,
    timeout: float,
    **kwargs: Any,
) -> T:
    try:
        if asyncio.iscoroutinefunction(func):
            return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
        else:
            loop = asyncio.get_running_loop()
            return await asyncio.wait_for(
                loop.run_in_executor(None, lambda: func(*args, **kwargs)),
                timeout=timeout
            )
    except asyncio.TimeoutError:
        raise TimeoutError(f"Operation timed out after {timeout}s")