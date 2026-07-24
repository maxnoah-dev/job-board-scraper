"""Retry logic with exponential backoff and full jitter.

Bounded retry with configurable retryable errors.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypeVar

import httpx  # noqa: F401

if TYPE_CHECKING:
    pass

T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_status_codes: tuple[int, ...] = field(
        default_factory=lambda: (408, 429, 500, 502, 503, 504)
    )
    retryable_exceptions: tuple[type[Exception], ...] = field(
        default_factory=lambda: (
            asyncio.TimeoutError,
            ConnectionError,
            TimeoutError,
        )
    )


def is_retryable_http_error(response: httpx.Response) -> bool:
    """Check if an HTTP error is retryable.

    Args:
        response: httpx Response object

    Returns:
        True if the error should be retried
    """
    return response.status_code in (408, 429, 500, 502, 503, 504)


def is_retryable_exception(exc: Exception) -> bool:
    """Check if an exception is retryable.

    Args:
        exc: Exception to check

    Returns:
        True if the error should be retried
    """
    retryable = (
        asyncio.TimeoutError,
        ConnectionError,
        TimeoutError,
    )
    return isinstance(exc, retryable)


def calculate_delay(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
) -> float:
    """Calculate delay for retry attempt with exponential backoff.

    Args:
        attempt: Current retry attempt (1-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay cap in seconds
        exponential_base: Base for exponential growth
        jitter: Whether to add random jitter

    Returns:
        Delay in seconds
    """
    delay = base_delay * (exponential_base ** (attempt - 1))
    delay = min(delay, max_delay)

    if jitter:
        # Full jitter: random value between 0 and delay
        delay = random.uniform(0, delay)

    return delay


async def retry_with_backoff(
    coro: Callable[..., T],
    config: RetryConfig | None = None,
    *args,
    **kwargs,
) -> T:
    """Execute a coroutine with retry logic.

    Args:
        coro: Coroutine to execute
        config: Retry configuration
        *args: Positional arguments for coro
        **kwargs: Keyword arguments for coro

    Returns:
        Result from coro

    Raises:
        The last exception if all retries fail
    """
    config = config or RetryConfig()
    last_exception: Exception | None = None

    for attempt in range(1, config.max_retries + 1):
        try:
            return await coro(*args, **kwargs)

        except Exception as exc:
            last_exception = exc

            # Check if retryable
            should_retry = False
            if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:  # type: ignore
                should_retry = is_retryable_http_error(exc.response)  # type: ignore
            else:
                should_retry = is_retryable_exception(exc)

            if not should_retry or attempt >= config.max_retries:
                raise

            # Calculate and apply delay
            delay = calculate_delay(
                attempt,
                config.base_delay,
                config.max_delay,
                config.exponential_base,
                config.jitter,
            )

            await asyncio.sleep(delay)

    if last_exception:
        raise last_exception
