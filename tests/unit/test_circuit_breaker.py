"""Unit tests for the circuit breaker utility (utils/circuit_breaker.py).

Covers:
- CircuitState enum
- CircuitBreakerConfig validation
- Circuit breaker CLOSED -> OPEN -> HALF_OPEN transitions
- CircuitBreakerOpenError
- Context manager and decorator usage
"""

from __future__ import annotations

import pytest

from job_board_scraper.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    CircuitState,
)

# ---------------------------------------------------------------------------
# CircuitBreakerConfig
# ---------------------------------------------------------------------------


class TestCircuitBreakerConfigValidation:
    """Config rejects invalid values."""

    def test_failure_threshold_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="failure_threshold must be >= 1"):
            CircuitBreakerConfig(failure_threshold=0)

    def test_recovery_timeout_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="recovery_timeout must be > 0"):
            CircuitBreakerConfig(recovery_timeout=0.0)

    def test_success_threshold_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="success_threshold must be >= 1"):
            CircuitBreakerConfig(success_threshold=0)

    def test_defaults_are_sensible(self) -> None:
        cfg = CircuitBreakerConfig()
        assert cfg.failure_threshold == 5
        assert cfg.recovery_timeout == 300.0
        assert cfg.success_threshold == 1


# ---------------------------------------------------------------------------
# CircuitState
# ---------------------------------------------------------------------------


class TestCircuitState:
    """CircuitState is a str Enum with three values."""

    def test_has_closed_state(self) -> None:
        assert CircuitState.CLOSED.value == "closed"

    def test_has_open_state(self) -> None:
        assert CircuitState.OPEN.value == "open"

    def test_has_half_open_state(self) -> None:
        assert CircuitState.HALF_OPEN.value == "half_open"

    def test_exactly_three_states(self) -> None:
        assert len(list(CircuitState)) == 3


# ---------------------------------------------------------------------------
# CircuitBreakerOpenError
# ---------------------------------------------------------------------------


class TestCircuitBreakerOpenError:
    """Error raised when circuit is open."""

    def test_message_includes_origin_and_retry_after(self) -> None:
        error = CircuitBreakerOpenError("example.com", retry_after=30.0)
        assert "example.com" in str(error)
        assert "30" in str(error)
        assert error.origin == "example.com"
        assert error.retry_after == 30.0


# ---------------------------------------------------------------------------
# CircuitBreaker transitions
# ---------------------------------------------------------------------------


class TestCircuitBreakerClosedState:
    """In CLOSED state, requests pass through and failures are tracked."""

    def test_starts_in_closed_state(self) -> None:
        cb = CircuitBreaker("test.example.com")
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self) -> None:
        cb = CircuitBreaker("test.example.com")
        # Record some failures
        await cb._record_failure()
        await cb._record_failure()
        assert cb._failure_count == 2
        # Success resets
        await cb._record_success()
        assert cb._failure_count == 0
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_failure_increments_counter(self) -> None:
        cb = CircuitBreaker(
            "test.example.com", CircuitBreakerConfig(failure_threshold=3)
        )
        assert cb._failure_count == 0
        await cb._record_failure()
        assert cb._failure_count == 1
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_trips_to_open_after_threshold(self) -> None:
        cb = CircuitBreaker(
            "test.example.com", CircuitBreakerConfig(failure_threshold=3)
        )
        for _ in range(3):
            await cb._record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb._opened_at is not None


class TestCircuitBreakerOpenState:
    """In OPEN state, requests are rejected immediately."""

    @pytest.mark.asyncio
    async def test_open_rejects_requests(self) -> None:
        cb = CircuitBreaker("test.example.com")
        cb._state = CircuitState.OPEN
        cb._opened_at = cb._time_monotonic()

        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            async with cb:
                pass  # should not reach here

        assert exc_info.value.origin == "test.example.com"

    @pytest.mark.asyncio
    async def test_retry_after_is_calculated(self) -> None:
        cb = CircuitBreaker(
            "test.example.com", CircuitBreakerConfig(recovery_timeout=60.0)
        )
        cb._state = CircuitState.OPEN
        cb._opened_at = cb._time_monotonic() - 30.0  # 30 seconds ago

        assert cb.retry_after is not None
        assert cb.retry_after == pytest.approx(30.0, abs=1.0)  # within 1 second


class TestCircuitBreakerHalfOpenState:
    """In HALF_OPEN state, one test request is allowed."""

    @pytest.mark.asyncio
    async def test_half_open_allows_request(self) -> None:
        cb = CircuitBreaker("test.example.com")
        cb._state = CircuitState.HALF_OPEN

        # Should not raise
        async with cb:
            pass

    @pytest.mark.asyncio
    async def test_success_in_half_open_closes_circuit(self) -> None:
        cb = CircuitBreaker(
            "test.example.com", CircuitBreakerConfig(success_threshold=1)
        )
        cb._state = CircuitState.HALF_OPEN
        cb._opened_at = cb._time_monotonic() - 300.0

        await cb._record_success()
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_failure_in_half_open_reopens_circuit(self) -> None:
        cb = CircuitBreaker("test.example.com")
        cb._state = CircuitState.HALF_OPEN
        cb._opened_at = cb._time_monotonic() - 300.0

        await cb._record_failure()
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_half_open_resets_success_counter(self) -> None:
        cb = CircuitBreaker(
            "test.example.com", CircuitBreakerConfig(success_threshold=2)
        )
        cb._state = CircuitState.HALF_OPEN
        cb._success_count = 1

        # Entering half-open (e.g. after recovery timeout)
        cb._state = CircuitState.OPEN
        cb._opened_at = cb._time_monotonic() - 300.0
        await cb._check_half_open_timer()

        assert cb._success_count == 0


class TestCircuitBreakerOpenToHalfOpenTransition:
    """OPEN -> HALF_OPEN transition after recovery timeout."""

    @pytest.mark.asyncio
    async def test_transitions_to_half_open_after_timeout(self) -> None:
        cb = CircuitBreaker(
            "test.example.com", CircuitBreakerConfig(recovery_timeout=5.0)
        )
        cb._state = CircuitState.OPEN
        cb._opened_at = cb._time_monotonic() - 10.0  # 10 seconds ago, timeout is 5

        await cb._check_half_open_timer()
        assert cb.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_stays_open_before_timeout(self) -> None:
        cb = CircuitBreaker(
            "test.example.com", CircuitBreakerConfig(recovery_timeout=60.0)
        )
        cb._state = CircuitState.OPEN
        cb._opened_at = cb._time_monotonic() - 30.0  # only 30 seconds elapsed

        await cb._check_half_open_timer()
        assert cb.state == CircuitState.OPEN


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


class TestCircuitBreakerContextManager:
    """CircuitBreaker as async context manager."""

    @pytest.mark.asyncio
    async def test_successful_context_records_success(self) -> None:
        cb = CircuitBreaker("test.example.com")

        async with cb:
            pass  # no exception

        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_exception_in_context_records_failure(self) -> None:
        cb = CircuitBreaker(
            "test.example.com", CircuitBreakerConfig(failure_threshold=2)
        )

        try:
            async with cb:
                raise RuntimeError("boom")
        except RuntimeError:
            pass

        assert cb._failure_count == 1


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------


class TestCircuitBreakerDecorator:
    """CircuitBreaker as a decorator."""

    @pytest.mark.asyncio
    async def test_decorator_wraps_function(self) -> None:
        cb = CircuitBreaker("test.example.com")

        @cb
        async def my_func() -> str:
            return "result"

        result = await my_func()
        assert result == "result"
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_decorator_opens_circuit_on_failure(self) -> None:
        cb = CircuitBreaker(
            "test.example.com", CircuitBreakerConfig(failure_threshold=2)
        )

        @cb
        async def failing_func() -> str:
            raise RuntimeError("boom")

        for i in range(2):
            try:
                await failing_func()
            except RuntimeError:
                pass

        assert cb.state == CircuitState.OPEN


# ---------------------------------------------------------------------------
# repr
# ---------------------------------------------------------------------------


class TestCircuitBreakerRepr:
    """repr shows useful debug information."""

    def test_repr_includes_origin_and_state(self) -> None:
        cb = CircuitBreaker("greenhouse.io")
        r = repr(cb)
        assert "greenhouse.io" in r
        assert "closed" in r
