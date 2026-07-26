"""Async VilaoLLM client.

Wraps the OpenAI Python SDK against the VilaoLLM base URL. Adds:

- Token-bucket rate limiting (default 60 req/min, configurable).
- Sequential-failure circuit breaker that disables the client after
  ``VILAO_FAIL_THRESHOLD`` consecutive errors.
- Pure async surface so it can be used directly from the ETL pipeline.

The client is intentionally narrow: it only exposes ``chat`` and
``close``. Higher-level helpers (e.g. title translation) live in
:mod:`job_board_scraper.llm.translator`.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openai import AsyncOpenAI  # pragma: no cover


class VilaoError(Exception):
    """Base error for Vilao LLM client failures."""


class VilaoRateLimitError(VilaoError):
    """Raised when the local rate limiter rejects an outbound request."""

    def __init__(self, retry_after: float) -> None:
        self.retry_after = retry_after
        super().__init__(
            f"Vilao rate limit reached; retry after {retry_after:.2f}s."
        )


class VilaoUnavailableError(VilaoError):
    """Raised when the circuit breaker is open."""


@dataclass
class VilaoClientConfig:
    """Configuration for :class:`VilaoClient`.

    Attributes:
        api_key: Vilao PAT. Empty string disables the client.
        base_url: OpenAI-compatible API base URL.
        model: Default model name.
        timeout_s: Per-request timeout in seconds.
        rate_limit_per_min: Soft rate limit; local limiter enforces this.
        fail_threshold: Consecutive failures that trip the circuit breaker.
    """

    api_key: str = ""
    base_url: str = "https://api.vilao.ai/v1"
    model: str = "gx/gpt-5.4"
    timeout_s: float = 15.0
    rate_limit_per_min: int = 60
    fail_threshold: int = 3

    @property
    def is_configured(self) -> bool:
        """Return True when an API key is present."""
        return bool(self.api_key and self.api_key.strip())


class _TokenBucket:
    """Minimal async token bucket for Vilao rate limiting."""

    def __init__(self, rate_per_minute: int) -> None:
        if rate_per_minute <= 0:
            raise ValueError("rate_per_minute must be > 0")
        self._rate = rate_per_minute / 60.0
        self._capacity = max(1.0, float(rate_per_minute))
        self._tokens = self._capacity
        self._lock = asyncio.Lock()
        self._last = time.monotonic()

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self._last
                self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
                self._last = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                wait = (1.0 - self._tokens) / self._rate if self._rate > 0 else 1.0
            await asyncio.sleep(wait)


class VilaoClient:
    """Async VilaoLLM client backed by the OpenAI Python SDK.

    The client is constructed with a :class:`VilaoClientConfig`. When the
    API key is empty, ``chat`` raises :class:`VilaoUnavailableError`
    immediately so callers can detect "feature disabled" without relying
    on env-var plumbing.

    Example::

        client = VilaoClient(VilaoClientConfig(api_key="..."))
        text = await client.chat("Xin chào")
        await client.close()
    """

    def __init__(self, config: VilaoClientConfig | None = None) -> None:
        self._config = config or VilaoClientConfig()
        self._bucket = _TokenBucket(self._config.rate_limit_per_min)
        self._consecutive_failures = 0
        self._circuit_open = False
        self._client: AsyncOpenAI | None = None
        self._closed = False

    # ─── Public properties ──────────────────────────────────────────────────
    @property
    def config(self) -> VilaoClientConfig:
        return self._config

    @property
    def is_available(self) -> bool:
        """Return True when the client can issue a request right now."""
        return self._config.is_configured and not self._circuit_open and not self._closed

    @property
    def circuit_open(self) -> bool:
        return self._circuit_open

    # ─── Lifecycle ──────────────────────────────────────────────────────────
    def _ensure_client(self) -> AsyncOpenAI:
        if self._client is None:
            from openai import AsyncOpenAI  # local import keeps tests light

            if not self._config.is_configured:
                raise VilaoUnavailableError("Vilao API key is not configured")
            self._client = AsyncOpenAI(
                api_key=self._config.api_key,
                base_url=self._config.base_url,
                timeout=self._config.timeout_s,
            )
        return self._client

    async def close(self) -> None:
        """Release the underlying HTTP client. Idempotent."""
        if self._closed:
            return
        self._closed = True
        if self._client is not None:
            close = getattr(self._client, "close", None)
            if close is None:
                return
            try:
                result = close()
            except TypeError:
                return
            if hasattr(result, "__await__"):
                await result

    # ─── Chat ───────────────────────────────────────────────────────────────
    async def chat(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 256,
    ) -> str:
        """Send a single-turn chat completion request.

        Args:
            prompt: User message.
            system: Optional system prompt. Prepended before the user message.
            temperature: Sampling temperature.
            max_tokens: Maximum number of tokens to generate.

        Returns:
            The model's text reply (stripped).

        Raises:
            VilaoUnavailableError: When the client is not configured or the
                circuit is open.
            VilaoError: For any underlying SDK error.
        """
        if not self._config.is_configured:
            raise VilaoUnavailableError("Vilao API key is not configured")
        if self._circuit_open:
            raise VilaoUnavailableError("Vilao circuit breaker is OPEN")
        if self._closed:
            raise VilaoUnavailableError("Vilao client is closed")

        await self._bucket.acquire()

        client = self._ensure_client()
        messages: list[dict[str, str]] = []  # type: ignore[list-item]
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await client.chat.completions.create(
                model=self._config.model,
                messages=messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:  # noqa: BLE001 — translate to VilaoError
            await self._record_failure()
            raise VilaoError(f"Vilao API call failed: {exc}") from exc

        self._consecutive_failures = 0
        text = self._extract_text(response)
        return text

    # ─── Helpers ────────────────────────────────────────────────────────────
    @staticmethod
    def _extract_text(response: object) -> str:
        """Extract the first message's text from an OpenAI response object."""
        try:
            choices = getattr(response, "choices", None)
            if not choices:
                return ""
            first = choices[0]
            message = getattr(first, "message", None)
            content = getattr(message, "content", None) if message is not None else None
            if content is None:
                return ""
            return str(content).strip()
        except Exception:  # pragma: no cover — defensive
            return ""

    async def _record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._config.fail_threshold:
            self._circuit_open = True
