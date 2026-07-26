"""Unit tests for ``adapters/protocols/api_adapter.py`` exercising the
generic fetch_jobs flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from job_board_scraper.adapters.base import ExtractionStatus
from job_board_scraper.adapters.protocols.api_adapter import ApiAdapter
from job_board_scraper.models.job import RawJobData


class _ConcreteApiAdapter(ApiAdapter):
    SLUG = "test-api"

    @property
    def slug(self) -> str:
        return self.SLUG

    def __init__(self, base_url: str = "https://example.com", **kwargs) -> None:
        super().__init__(base_url=base_url, **kwargs)
        self._page_size = 2
        self._fake_payloads: list[dict] = []

    def set_payloads(self, payloads: list[dict]) -> None:
        self._fake_payloads = payloads

    def _get_listing_url(self, page: int = 1, per_page: int = 100) -> str:
        return f"{self.base_url}/jobs?page={page}&per_page={self._page_size}"

    def _parse_jobs(self, response_data):
        return [
            RawJobData(
                source_company_id=self.slug,
                title=f"Job-{j['id']}",
                url=f"{self.base_url}/j/{j['id']}",
            )
            for j in response_data.get("jobs", [])
        ]

    def _get_pagination(self, response_data):
        if not response_data.get("jobs"):
            return None
        total = response_data.get("total", 0)
        fetched = response_data.get("offset", 0) + len(response_data["jobs"])
        if fetched >= total:
            return None
        return {"has_next": True}

    async def close(self) -> None:
        """No-op for API adapter — httpx client is closed per-fetch."""
        return None


def _adapter(payloads: list[dict]) -> _ConcreteApiAdapter:
    a = _ConcreteApiAdapter()
    a.set_payloads(payloads)
    return a


def _mock_response(data: dict, status_code: int = 200) -> httpx.Response:
    request = httpx.Request("GET", "https://example.com")
    return httpx.Response(status_code, json=data, request=request)


class TestApiAdapterProperties:
    def test_adapter_type(self) -> None:
        a = _ConcreteApiAdapter()
        assert a.adapter_type == "api"
        assert a.base_url == "https://example.com"


class TestApiAdapterFetchJobs:
    @pytest.mark.asyncio
    async def test_fetch_jobs_first_page_only(self) -> None:
        a = _adapter([
            {
                "jobs": [{"id": 1}, {"id": 2}],
                "total": 2,
                "offset": 0,
            }
        ])
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_mock_response(a._fake_payloads[0]))):
            result = await a.fetch_jobs()
        assert result.status == ExtractionStatus.SUCCESS
        assert [j.title for j in result.jobs] == ["Job-1", "Job-2"]

    @pytest.mark.asyncio
    async def test_fetch_jobs_pagination(self) -> None:
        a = _adapter([
            {"jobs": [{"id": 1}, {"id": 2}], "total": 4, "offset": 0},
            {"jobs": [{"id": 3}, {"id": 4}], "total": 4, "offset": 2},
        ])
        responses = [
            _mock_response(a._fake_payloads[0]),
            _mock_response(a._fake_payloads[1]),
        ]
        side_effect_iter = iter(responses)

        async def fake_get(self, url):
            return next(side_effect_iter)

        with patch.object(httpx.AsyncClient, "get", new=fake_get):
            result = await a.fetch_jobs()
        assert len(result.jobs) == 4
        assert result.pages_fetched == 2

    @pytest.mark.asyncio
    async def test_fetch_jobs_rate_limited(self) -> None:
        a = _adapter([{"jobs": [{"id": 1}], "total": 1, "offset": 0}])
        rl = MagicMock()
        rl.acquire = AsyncMock()
        a._rate_limiter = rl
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_mock_response({}, status_code=429))):
            result = await a.fetch_jobs()
        assert any("Rate limited" in w for w in result.warnings)
        assert result.status == ExtractionStatus.FAILED

    @pytest.mark.asyncio
    async def test_fetch_jobs_auth_failed_401(self) -> None:
        a = _adapter([])
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_mock_response({}, status_code=401))):
            result = await a.fetch_jobs()
        assert result.status == ExtractionStatus.FAILED
        assert "Authentication failed" in (result.error or "")

    @pytest.mark.asyncio
    async def test_fetch_jobs_auth_failed_403(self) -> None:
        a = _adapter([])
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_mock_response({}, status_code=403))):
            result = await a.fetch_jobs()
        assert result.status == ExtractionStatus.FAILED

    @pytest.mark.asyncio
    async def test_fetch_jobs_http_error(self) -> None:
        a = _adapter([])
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_mock_response({}, status_code=500))):
            result = await a.fetch_jobs()
        assert any("HTTP error" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_fetch_jobs_timeout(self) -> None:
        a = _adapter([])

        async def raise_timeout(self, url):
            raise httpx.TimeoutException("boom")

        with patch.object(httpx.AsyncClient, "get", new=raise_timeout):
            result = await a.fetch_jobs()
        assert any("Timeout" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_fetch_jobs_unexpected_error(self) -> None:
        a = _adapter([])

        async def raise_error(self, url):
            raise RuntimeError("oops")

        with patch.object(httpx.AsyncClient, "get", new=raise_error):
            result = await a.fetch_jobs()
        assert any("Error on page" in w for w in result.warnings)
