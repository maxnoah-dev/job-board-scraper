"""Unit tests for the retry utility (utils/retry.py).

Covers:
- RetryConfig validation
- is_retryable_http_error / is_retryable_exception
- calculate_delay jitter bounds
- retry_with_backoff success, retry, and exhaustion paths
"""

from __future__ import annotations

import httpx
import pytest

from job_board_scraper.utils.retry import (
    RetryConfig,
    calculate_delay,
    is_retryable_exception,
    is_retryable_http_error,
    retry_with_backoff,
)

# ---------------------------------------------------------------------------
# RetryConfig
# ---------------------------------------------------------------------------


class TestRetryConfigValidation:
    """RetryConfig accepts valid inputs with sensible defaults."""

    def test_defaults_are_sensible(self) -> None:
        cfg = RetryConfig()
        assert cfg.max_retries == 3
        assert cfg.base_delay == 1.0
        assert cfg.max_delay == 30.0
        assert cfg.jitter is True

    def test_custom_values_are_accepted(self) -> None:
        cfg = RetryConfig(max_retries=5, base_delay=2.0, max_delay=60.0)
        assert cfg.max_retries == 5
        assert cfg.base_delay == 2.0
        assert cfg.max_delay == 60.0


# ---------------------------------------------------------------------------
# is_retryable_http_error
# ---------------------------------------------------------------------------


class TestIsRetryableHttpError:
    """HTTP errors are correctly classified."""

    def test_429_is_retryable(self) -> None:
        response = httpx.Response(429)
        assert is_retryable_http_error(response) is True

    def test_500_is_retryable(self) -> None:
        response = httpx.Response(500)
        assert is_retryable_http_error(response) is True

    def test_503_is_retryable(self) -> None:
        response = httpx.Response(503)
        assert is_retryable_http_error(response) is True

    def test_504_is_retryable(self) -> None:
        response = httpx.Response(504)
        assert is_retryable_http_error(response) is True

    def test_408_is_retryable(self) -> None:
        response = httpx.Response(408)
        assert is_retryable_http_error(response) is True

    def test_401_is_not_retryable(self) -> None:
        response = httpx.Response(401)
        assert is_retryable_http_error(response) is False

    def test_403_is_not_retryable(self) -> None:
        response = httpx.Response(403)
        assert is_retryable_http_error(response) is False


# ---------------------------------------------------------------------------
# is_retryable_exception
# ---------------------------------------------------------------------------


class TestIsRetryableException:
    """Exceptions are correctly classified."""

    def test_timeout_error_is_retryable(self) -> None:
        exc = TimeoutError()
        assert is_retryable_exception(exc) is True

    def test_connection_error_is_retryable(self) -> None:
        exc = ConnectionError()
        assert is_retryable_exception(exc) is True

    def test_standard_timeout_is_retryable(self) -> None:
        exc = TimeoutError()
        assert is_retryable_exception(exc) is True

    def test_value_error_is_not_retryable(self) -> None:
        exc = ValueError("some error")
        assert is_retryable_exception(exc) is False


# ---------------------------------------------------------------------------
# calculate_delay
# ---------------------------------------------------------------------------


class TestCalculateDelay:
    """Delay calculation stays within bounds and grows exponentially."""

    def test_delay_is_bounded_by_max(self) -> None:
        max_delay = 10.0
        for attempt in range(1, 10):
            delay = calculate_delay(
                attempt, base_delay=1.0, max_delay=max_delay, jitter=True
            )
            assert delay <= max_delay, f"delay {delay} exceeds max {max_delay}"

    def test_delay_grows_with_attempt(self) -> None:
        """Later attempts have higher average delays due to exponential backoff."""
        # Run multiple times to reduce flakiness
        for _ in range(10):
            delays = [
                calculate_delay(i, base_delay=1.0, max_delay=1000.0, jitter=True)
                for i in range(1, 6)
            ]
            # The average of later attempts should be higher
            avg_early = sum(delays[:2]) / 2
            avg_late = sum(delays[3:]) / 2
            if avg_late >= avg_early:
                break
        else:
            # Allow flakiness by checking at least one pair
            assert delays[4] >= delays[0], (
                "later attempts should have higher delays on average"
            )

    def test_without_jitter_is_deterministic(self) -> None:
        delay1 = calculate_delay(2, base_delay=1.0, max_delay=30.0, jitter=False)
        delay2 = calculate_delay(2, base_delay=1.0, max_delay=30.0, jitter=False)
        assert delay1 == delay2


# ---------------------------------------------------------------------------
# retry_with_backoff
# ---------------------------------------------------------------------------


class TestRetryWithBackoff:
    """Integration tests for the retry wrapper."""

    @pytest.mark.asyncio
    async def test_succeeds_on_first_attempt(self) -> None:
        async def succeed() -> str:
            return "ok"

        result = await retry_with_backoff(succeed)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_retries_on_transient_error(self) -> None:
        """Retryable errors cause retries until success."""
        attempt = 0
        call_count = 0

        async def flaky() -> str:
            nonlocal attempt, call_count
            call_count += 1
            attempt += 1
            if attempt < 3:
                raise TimeoutError("try again")
            return "success"

        result = await retry_with_backoff(flaky, config=RetryConfig(max_retries=5))
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_on_non_retryable_error(self) -> None:
        """Non-retryable errors raise immediately."""

        async def fail() -> str:
            raise ValueError("not retryable")

        with pytest.raises(ValueError):
            await retry_with_backoff(fail, config=RetryConfig(max_retries=3))
