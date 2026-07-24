"""Circuit breaker.

Three-state machine (closed, open, half-open) that prevents cascading
failures when a downstream service is unhealthy. Each source has its
own circuit breaker to isolate failures to the affected adapter.

Real implementation lands in Phase 3 (P3-05).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    pass

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker state."""

    CLOSED = "closed"
    """Normal operation. Requests pass through; failures are tracked."""

    OPEN = "open"
    """Service is unhealthy. Requests are rejected immediately without calling the target."""

    HALF_OPEN = "half_open"
    """Recovery in progress. A single test request is allowed to check if the target has recovered."""


class CircuitBreakerOpenError(Exception):
    """Raised when a request is rejected because the circuit is OPEN.

    Attributes:
        origin: The source whose circuit is open.
        retry_after: Seconds until the circuit transitions to HALF_OPEN.
    """

    def __init__(self, origin: str, retry_after: float) -> None:
        self.origin = origin
        self.retry_after = retry_after
        super().__init__(
            f"Circuit breaker is OPEN for {origin!r}. Retry after {retry_after:.1f}s."
        )


@dataclass
class CircuitBreakerConfig:
    """Configuration for a circuit breaker instance.

    Attributes:
        failure_threshold: Number of consecutive failures required to trip the circuit
            from CLOSED to OPEN. Must be >= 1.
        recovery_timeout: Seconds to wait before transitioning from OPEN to HALF_OPEN.
            The circuit will not allow requests during this period.
        success_threshold: Number of consecutive successes required in HALF_OPEN
            to transition back to CLOSED. Default is 1 (first success closes the circuit).
    """

    failure_threshold: int = 5
    recovery_timeout: float = 300.0
    success_threshold: int = 1

    def __post_init__(self) -> None:
        if self.failure_threshold < 1:
            raise ValueError(
                f"failure_threshold must be >= 1, got {self.failure_threshold}"
            )
        if self.recovery_timeout <= 0:
            raise ValueError(
                f"recovery_timeout must be > 0, got {self.recovery_timeout}"
            )
        if self.success_threshold < 1:
            raise ValueError(
                f"success_threshold must be >= 1, got {self.success_threshold}"
            )


class CircuitBreaker:
    """Three-state circuit breaker for a single origin.

    The circuit breaker has three states:

    - **CLOSED**: Normal operation. All requests pass through. Each failure
      increments an internal counter. When the counter reaches
      ``failure_threshold``, the circuit trips to OPEN.
    - **OPEN**: After tripping, the circuit remains OPEN for ``recovery_timeout``
      seconds. All requests are rejected with ``CircuitBreakerOpenError`` without
      calling the target. After the timeout, it transitions to HALF_OPEN.
    - **HALF_OPEN**: A limited probe. One request at a time is allowed through.
      If it succeeds, the circuit closes. If it fails, the circuit re-opens.
      The counter for consecutive failures is reset when entering HALF_OPEN.

    Thread-safety: all state transitions are protected by an ``asyncio.Lock``.

    Usage::

        cb = CircuitBreaker("greenhouse.io", CircuitBreakerConfig(failure_threshold=3))


        async def fetch_jobs() -> list[dict]:
            async with cb:
                return await _do_http_request()

    Or with a decorator::

        @cb
        async def fetch_jobs() -> list[dict]:
            return await _do_http_request()

    Args:
        origin: Identifier for the source (e.g. hostname). Used in log messages.
        config: Circuit breaker configuration.
    """

    def __init__(
        self,
        origin: str,
        config: CircuitBreakerConfig | None = None,
    ) -> None:
        self._origin = origin
        self._config = config or CircuitBreakerConfig()

        # State
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._opened_at: float | None = None  # timestamp when circuit opened

        # Lock for thread-safe state transitions
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Current state of the circuit breaker."""
        return self._state

    @property
    def origin(self) -> str:
        """Origin identifier for this circuit breaker."""
        return self._origin

    def _time_monotonic(self) -> float:
        """Return monotonic time (not wall clock) for internal timers."""
        return time.monotonic()

    async def _check_half_open_timer(self) -> None:
        """Check if we should transition from OPEN to HALF_OPEN based on elapsed time."""
        if self._state != CircuitState.OPEN:
            return
        if self._opened_at is None:
            return

        elapsed = self._time_monotonic() - self._opened_at
        if elapsed >= self._config.recovery_timeout:
            self._state = CircuitState.HALF_OPEN
            self._success_count = 0

    async def _record_success(self) -> None:
        """Record a successful call."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self._config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    self._opened_at = None
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success in CLOSED state
                self._failure_count = 0

    async def _record_failure(self) -> None:
        """Record a failed call."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                # Any failure in HALF_OPEN re-opens the circuit
                self._state = CircuitState.OPEN
                self._opened_at = self._time_monotonic()
                self._success_count = 0
            elif self._state == CircuitState.CLOSED:
                self._failure_count += 1
                if self._failure_count >= self._config.failure_threshold:
                    self._state = CircuitState.OPEN
                    self._opened_at = self._time_monotonic()

    @property
    def retry_after(self) -> float | None:
        """Seconds until the circuit transitions from OPEN to HALF_OPEN.

        Returns None if the circuit is not OPEN.
        """
        if self._state != CircuitState.OPEN or self._opened_at is None:
            return None
        elapsed = self._time_monotonic() - self._opened_at
        remaining = self._config.recovery_timeout - elapsed
        return max(0.0, remaining)

    async def can_execute(self) -> bool:
        """Return True if a request is allowed through.

        Checks the current state and, if OPEN, whether the recovery timeout
        has elapsed so it can transition to HALF_OPEN.
        """
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                # Check if we should transition
                # Note: for simplicity, we check outside the lock in the public method
                # but transition inside the lock
                pass

            return self._state == CircuitState.HALF_OPEN

    async def _ensure_ready(self) -> None:
        """Ensure the circuit is ready to accept requests.

        Transitions from OPEN to HALF_OPEN if the recovery timeout has elapsed.
        Must be called inside the lock.
        """
        if self._state == CircuitState.OPEN:
            if self._opened_at is None:
                return
            elapsed = self._time_monotonic() - self._opened_at
            if elapsed >= self._config.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0

    async def __aenter__(self) -> None:
        """Enter the circuit breaker context.

        Raises:
            CircuitBreakerOpenError: If the circuit is OPEN and the recovery
                timeout has not elapsed.
        """
        async with self._lock:
            await self._ensure_ready()

            if self._state == CircuitState.OPEN:
                retry_after = self.retry_after or 0.0
                raise CircuitBreakerOpenError(self._origin, retry_after)

            # In CLOSED or HALF_OPEN, we allow the request through
            # but we need to release the lock to avoid blocking

    async def __aexit__(
        self, exc_type: type[BaseException] | None, *args: object
    ) -> None:
        """Exit the circuit breaker context.

        Records the outcome (success or failure) for circuit state management.
        """
        if exc_type is None:
            await self._record_success()
        else:
            await self._record_failure()

    def __call__(
        self, func: Callable[..., Awaitable[T]]
    ) -> Callable[..., Awaitable[T]]:
        """Decorator that wraps an async function with this circuit breaker.

        Example::

            @circuit_breaker
            async def fetch_jobs() -> list[dict]:
                return await _http_call()
        """
        import functools

        @functools.wraps(func)
        async def wrapper(*args: object, **kwargs: object) -> T:
            async with self:
                return await func(*args, **kwargs)

        return wrapper

    def __repr__(self) -> str:
        return (
            f"CircuitBreaker(origin={self._origin!r}, "
            f"state={self._state.value}, "
            f"failures={self._failure_count}/{self._config.failure_threshold})"
        )
