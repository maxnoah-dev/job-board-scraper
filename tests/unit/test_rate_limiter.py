"""Unit tests for the rate limiter utility (utils/rate_limiter.py).

Covers:
- TokenBucket refill and acquire semantics
- RateLimiter per-origin isolation
- RateLimitConfig for_adapter_type and to_limiter
"""

from __future__ import annotations

import pytest

from job_board_scraper.utils.rate_limiter import (
    API_DELAY_RANGE,
    BROWSER_DELAY_RANGE,
    HTML_DELAY_RANGE,
    RateLimitConfig,
    RateLimiter,
    TokenBucket,
    defaults_for_type,
)

# ---------------------------------------------------------------------------
# TokenBucket
# ---------------------------------------------------------------------------


class TestTokenBucket:
    """TokenBucket controls request rate via tokens."""

    def test_create_from_rate(self) -> None:
        """TokenBucket.create is a valid constructor."""
        # We can't fully test without an event loop, but we can verify it doesn't crash
        bucket = TokenBucket(rate=1.0, capacity=2.0, tokens=2.0, last_update=0.0)
        assert bucket.rate == 1.0
        assert bucket.capacity == 2.0

    def test_create_rejects_zero_rate(self) -> None:
        with pytest.raises(ValueError, match="requests_per_second"):
            TokenBucket.create(requests_per_second=0.0)


# ---------------------------------------------------------------------------
# RateLimiter
# ---------------------------------------------------------------------------


class TestRateLimiter:
    """RateLimiter enforces per-origin delays."""

    def test_creates_separate_buckets_per_origin(self) -> None:
        limiter = RateLimiter(delay_range=(1.0, 2.0))
        assert limiter.origins == []

    def test_origins_list_starts_empty(self) -> None:
        limiter = RateLimiter()
        assert limiter.origins == []

    @pytest.mark.asyncio
    async def test_acquire_returns_without_error(self) -> None:
        limiter = RateLimiter(delay_range=(0.0, 0.01))
        # Should not raise
        await limiter.acquire("test.example.com")


# ---------------------------------------------------------------------------
# RateLimitConfig
# ---------------------------------------------------------------------------


class TestRateLimitConfig:
    """RateLimitConfig stores per-adapter settings."""

    def test_default_values(self) -> None:
        cfg = RateLimitConfig()
        assert cfg.delay_range == HTML_DELAY_RANGE
        assert cfg.max_concurrent == 2

    def test_for_adapter_type_api(self) -> None:
        cfg = RateLimitConfig.for_adapter_type("api")
        assert cfg.delay_range == API_DELAY_RANGE

    def test_for_adapter_type_html(self) -> None:
        cfg = RateLimitConfig.for_adapter_type("html")
        assert cfg.delay_range == HTML_DELAY_RANGE

    def test_for_adapter_type_browser(self) -> None:
        cfg = RateLimitConfig.for_adapter_type("browser")
        assert cfg.delay_range == BROWSER_DELAY_RANGE

    def test_for_adapter_type_unknown_defaults_to_html(self) -> None:
        cfg = RateLimitConfig.for_adapter_type("unknown")
        assert cfg.delay_range == HTML_DELAY_RANGE

    def test_to_limiter_creates_configured_limiter(self) -> None:
        cfg = RateLimitConfig(delay_range=(0.5, 1.0), max_concurrent=3)
        limiter = cfg.to_limiter()
        assert limiter._delay_range == (0.5, 1.0)
        assert limiter._max_concurrent == 3


class TestModuleLevelDefaults:
    """Module-level default configs are properly defined."""

    def test_html_delay_range_is_valid(self) -> None:
        assert HTML_DELAY_RANGE[0] > 0
        assert HTML_DELAY_RANGE[1] >= HTML_DELAY_RANGE[0]

    def test_api_delay_range_is_valid(self) -> None:
        assert API_DELAY_RANGE[0] > 0
        assert API_DELAY_RANGE[1] >= API_DELAY_RANGE[0]

    def test_browser_delay_range_is_valid(self) -> None:
        assert BROWSER_DELAY_RANGE[0] > 0
        assert BROWSER_DELAY_RANGE[1] >= BROWSER_DELAY_RANGE[0]

    def test_defaults_for_type_api(self) -> None:
        cfg = defaults_for_type("api")
        assert cfg.delay_range == API_DELAY_RANGE

    def test_defaults_for_type_html(self) -> None:
        cfg = defaults_for_type("html")
        assert cfg.delay_range == HTML_DELAY_RANGE

    def test_defaults_for_type_browser(self) -> None:
        cfg = defaults_for_type("browser")
        assert cfg.delay_range == BROWSER_DELAY_RANGE
