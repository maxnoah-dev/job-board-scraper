"""Async HTTP client with configurable timeouts and connection pooling.

Wraps ``httpx.AsyncClient`` with:
- Context manager pattern for lifecycle management
- Automatic timeout configuration
- Sensitive URL redaction in logs
- Connection pooling (shared client across requests)

Real implementation lands in Phase 3 (P3-02).
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx

# Pattern to redact API keys, tokens, and numeric IDs from URLs in logs
_URL_REDACT_PATTERN = re.compile(
    r"([?&](?:api[_-]?key|token|secret|password|auth|key|id)=)[^&]+",
    re.IGNORECASE,
)


def _redact_url(url: str) -> str:
    """Redact sensitive query parameters from a URL for safe logging."""
    return _URL_REDACT_PATTERN.sub(r"\1<REDACTED>", url)


DEFAULT_TIMEOUT = httpx.Timeout(timeout=30.0, connect=10.0)
"""Default timeout: 30s total, 10s for connection establishment."""


class HttpClient:
    """Async HTTP client with configurable timeouts and connection pooling.

    This class wraps ``httpx.AsyncClient`` to provide:
    - Shared connection pool (fewer TCP handshakes)
    - Automatic timeout enforcement
    - Safe URL logging (sensitive params redacted)
    - Graceful shutdown via ``.aclose()``

    Use as an async context manager::

        async with HttpClient() as client:
            response = await client.get("https://api.example.com/jobs")
            jobs = response.json()

    Attributes:
        timeout: Default ``httpx.Timeout`` applied to all requests.
        limits: Connection pool limits.
        follow_redirects: Whether to follow HTTP redirects (default True).
    """

    def __init__(
        self,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
        max_connections: int = 100,
        max_keepalive_connections: int = 20,
        follow_redirects: bool = True,
    ) -> None:
        self._timeout = timeout
        self._limits = httpx.Limits(
            max_connections=max_connections,
            max_keepalive_connections=max_keepalive_connections,
        )
        self._follow_redirects = follow_redirects
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Lazily initialized ``httpx.AsyncClient`` (created on first request)."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                limits=self._limits,
                follow_redirects=self._follow_redirects,
            )
        return self._client

    async def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | float | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Send a GET request.

        Args:
            url: Target URL.
            params: Query string parameters.
            headers: Additional HTTP headers.
            timeout: Override the default timeout for this request.
            **kwargs: Forwarded to ``httpx.AsyncClient.get``.

        Returns:
            ``httpx.Response`` object. Always check ``response.status_code``
            before accessing ``response.json()`` or ``response.text()``.
        """
        return await self.client.get(
            url,
            params=params,
            headers=headers,
            timeout=timeout,
            **kwargs,
        )

    async def post(
        self,
        url: str,
        *,
        json: dict[str, Any] | list | None = None,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | float | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Send a POST request.

        Args:
            url: Target URL.
            json: JSON-serializable body.
            data: Form-encoded body.
            params: Query string parameters.
            headers: Additional HTTP headers.
            timeout: Override the default timeout for this request.
            **kwargs: Forwarded to ``httpx.AsyncClient.post``.

        Returns:
            ``httpx.Response`` object.
        """
        return await self.client.post(
            url,
            json=json,
            data=data,
            params=params,
            headers=headers,
            timeout=timeout,
            **kwargs,
        )

    async def head(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | float | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Send a HEAD request (fetch headers only).

        Useful for checking resource existence or fetching content-length
        without downloading the full body.

        Args:
            url: Target URL.
            params: Query string parameters.
            headers: Additional HTTP headers.
            timeout: Override the default timeout for this request.

        Returns:
            ``httpx.Response`` object.
        """
        return await self.client.head(
            url,
            params=params,
            headers=headers,
            timeout=timeout,
            **kwargs,
        )

    async def aclose(self) -> None:
        """Close the HTTP client and release all connections.

        Call this when the client is no longer needed to prevent resource leaks.
        Idempotent: calling on an already-closed client is a no-op.
        """
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> HttpClient:
        """Async context manager entry — returns self."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit — ensures cleanup."""
        await self.aclose()


@asynccontextmanager
async def http_client(
    timeout: httpx.Timeout = DEFAULT_TIMEOUT,
    **kwargs: Any,
) -> AsyncIterator[HttpClient]:
    """Create a temporary HTTP client with automatic cleanup.

    Convenience factory that wraps ``HttpClient`` in an async context manager::

        async with http_client() as client:
            response = await client.get("https://api.example.com/jobs")

    Args:
        timeout: Default ``httpx.Timeout`` applied to all requests.
        **kwargs: Forwarded to ``HttpClient.__init__``.

    Yields:
        Configured ``HttpClient`` instance.
    """
    client = HttpClient(timeout=timeout, **kwargs)
    try:
        yield client
    finally:
        await client.aclose()
