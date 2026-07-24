"""Per-origin rate limiter.

Async semaphore-based rate limiter that enforces per-source
min-interval delays and per-origin concurrency caps. Integrates with
the HTTP client wrapper so requests are automatically spaced.

Real implementation lands in Phase 3 (P3-04).
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# Default delay ranges per adapter type (seconds).
# API adapters can be more aggressive since they are designed for programmatic access.
API_DELAY_RANGE = (0.5, 1.0)
"""Typical range for API/ATS integrations (Greenhouse, Lever, etc.)."""

HTML_DELAY_RANGE = (2.0, 4.0)
"""Typical range for static HTML scraping."""

BROWSER_DELAY_RANGE = (3.0, 6.0)
"""Typical range for browser automation (anti-bot sites)."""


def _random_delay(min_delay: float, max_delay: float) -> float:
    """Return a random float in [min_delay, max_delay]."""
    return random.uniform(min_delay, max_delay)


@dataclass
class TokenBucket:
    """Token bucket for a single origin.

    A token bucket controls the rate of requests to a single origin.
    Tokens are added at a steady rate (``rate`` per second) up to ``capacity``.
    Each request consumes one token. If no tokens are available, the caller
    waits until one becomes available.

    Attributes:
        rate: Rate at which tokens are added per second.
        capacity: Maximum number of tokens (and initial burst size).
        tokens: Current number of available tokens.
        last_update: Timestamp of the last token refill (seconds since epoch).
    """

    rate: float
    capacity: float
    tokens: float
    last_update: float

    @classmethod
    def create(
        cls, requests_per_second: float, burst: float | None = None
    ) -> TokenBucket:
        """Create a token bucket from a target requests-per-second rate.

        Args:
            requests_per_second: Target rate (e.g. 0.5 = one request every 2 seconds).
            burst: Maximum burst size. Defaults to ``requests_per_second * 2``.
        """
        if requests_per_second <= 0:
            raise ValueError(
                f"requests_per_second must be > 0, got {requests_per_second}"
            )
        if burst is None:
            burst = max(1.0, requests_per_second * 2)
        return cls(
            rate=requests_per_second,
            capacity=burst,
            tokens=burst,
            last_update=_time_monotonic(),
        )

    def _refill(self) -> None:
        """Refill tokens based on elapsed time since last update."""
        now = _time_monotonic()
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_update = now

    async def acquire(self) -> None:
        """Wait until at least one token is available, then consume it."""
        while True:
            self._refill()
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return
            # Wait until the next token will be available
            wait_time = (1.0 - self.tokens) / self.rate
            await asyncio.sleep(wait_time)


def _time_monotonic() -> float:
    """Return monotonic time in seconds (same clock as asyncio.sleep)."""
    return asyncio.get_running_loop().time()


class RateLimiter:
    """Per-origin rate limiter using token buckets.

    ``RateLimiter`` maintains a separate token bucket for each origin (host).
    This prevents a single misbehaving adapter from starving others and allows
    different adapters to use different rate limits.

    Usage::

        limiter = RateLimiter()
        await limiter.acquire("greenhouse.io")
        response = await client.get("https://boards-api.greenhouse.io/v1/jobs")

    Or with a delay range::

        limiter = RateLimiter(delay_range=HTML_DELAY_RANGE)
        await limiter.acquire("example.com")
        response = await client.get("https://example.com/jobs")

    Args:
        delay_range: Min and max delay in seconds between requests to the same origin.
            Defaults to ``HTML_DELAY_RANGE``.
        max_concurrent_per_origin: Maximum concurrent requests to a single origin.
            Defaults to 2.
    """

    def __init__(
        self,
        delay_range: tuple[float, float] | None = None,
        max_concurrent_per_origin: int = 2,
    ) -> None:
        self._delay_range = delay_range or HTML_DELAY_RANGE
        self._max_concurrent = max_concurrent_per_origin

        # Per-origin state
        self._buckets: dict[str, TokenBucket] = {}
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, origin: str) -> None:
        """Wait until the rate limit allows a new request to ``origin``.

        This method is coroutine-safe and may be called concurrently from
        multiple tasks. It blocks the calling coroutine until the request
        is permitted.

        Args:
            origin: The host/authority part of a URL (e.g. ``"boards-api.greenhouse.io"``).
                Used as the key for per-origin rate limiting.
        """
        bucket, semaphore = await self._get_or_create(origin)

        # Acquire semaphore slot (limits concurrency)
        await semaphore.acquire()
        try:
            # Acquire token (limits rate)
            await bucket.acquire()
        except BaseException:
            semaphore.release()
            raise

    async def _get_or_create(
        self, origin: str
    ) -> tuple[TokenBucket, asyncio.Semaphore]:
        """Get or create a bucket and semaphore for an origin."""
        async with self._lock:
            if origin not in self._buckets:
                # Convert delay range to a rate
                min_delay, max_delay = self._delay_range
                avg_delay = (min_delay + max_delay) / 2
                requests_per_second = 1.0 / avg_delay if avg_delay > 0 else 1.0

                self._buckets[origin] = TokenBucket.create(requests_per_second)
                self._semaphores[origin] = asyncio.Semaphore(self._max_concurrent)

            return self._buckets[origin], self._semaphores[origin]

    async def release(self, origin: str) -> None:
        """Release the semaphore slot for an origin.

        Call this when a request completes to allow the next request to proceed.
        Usually you do not need to call this directly; use ``acquire`` with
        a context manager or ensure you call ``release`` in a ``finally`` block.

        Args:
            origin: The origin whose semaphore slot to release.
        """
        async with self._lock:
            if origin in self._semaphores:
                self._semaphores[origin].release()

    @property
    def origins(self) -> list[str]:
        """Return all origins currently being rate-limited."""
        return list(self._buckets.keys())


@dataclass
class RateLimitConfig:
    """Per-adapter rate limit configuration.

    Attributes:
        delay_range: Min and max seconds between consecutive requests.
        max_concurrent: Maximum concurrent requests to the same origin.
    """

    delay_range: tuple[float, float] = field(default_factory=lambda: HTML_DELAY_RANGE)
    max_concurrent: int = 2

    @classmethod
    def for_adapter_type(cls, adapter_type: str) -> RateLimitConfig:
        """Return a pre-configured rate limit for a known adapter type.

        Args:
            adapter_type: One of ``"api"``, ``"html"``, ``"browser"``.

        Returns:
            ``RateLimitConfig`` with appropriate defaults for that type.
        """
        if adapter_type == "api":
            return cls(delay_range=API_DELAY_RANGE, max_concurrent=4)
        if adapter_type == "browser":
            return cls(delay_range=BROWSER_DELAY_RANGE, max_concurrent=2)
        return cls(delay_range=HTML_DELAY_RANGE, max_concurrent=2)

    def to_limiter(self) -> RateLimiter:
        """Create a ``RateLimiter`` from this configuration."""
        return RateLimiter(
            delay_range=self.delay_range,
            max_concurrent_per_origin=self.max_concurrent,
        )


def defaults_for_type(adapter_type: str) -> RateLimitConfig:
    """Return the default ``RateLimitConfig`` for a given adapter type.

    Args:
        adapter_type: One of ``"api"``, ``"html"``, ``"browser"``.

    Returns:
        ``RateLimitConfig`` with type-appropriate defaults.
    """
    return RateLimitConfig.for_adapter_type(adapter_type)
