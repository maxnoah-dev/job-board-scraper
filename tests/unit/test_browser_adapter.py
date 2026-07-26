"""Unit tests for ``adapters/protocols/browser_adapter.py`` focusing on
abstract behaviour via a concrete subclass."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from job_board_scraper.adapters.protocols.browser_adapter import BrowserAdapter
from job_board_scraper.models.job import RawJobData
from job_board_scraper.utils.browser import AntiBotDetection


class _ConcreteAdapter(BrowserAdapter):
    """Minimal concrete subclass used to exercise abstract-base defaults."""

    SLUG = "test"

    @property
    def slug(self) -> str:
        return self.SLUG

    def _get_listing_url(self, page: int = 1) -> str:
        return f"https://example.com/jobs?page={page}"

    def _parse_jobs(self, page_content):
        return [
            RawJobData(
                source_company_id=self.slug,
                title="Engineer",
                url="https://example.com/1",
            )
        ]


def _adapter() -> _ConcreteAdapter:
    return _ConcreteAdapter(base_url="https://example.com")


class TestBrowserAdapterProperties:
    def test_adapter_type_is_browser(self) -> None:
        a = _adapter()
        assert a.adapter_type == "browser"
        assert a.base_url == "https://example.com"
        assert a.is_started is False
        assert a.screenshot_dir is None

    def test_listing_url_uses_page(self) -> None:
        a = _adapter()
        assert a._get_listing_url(3) == "https://example.com/jobs?page=3"


class TestBrowserAdapterHooks:
    def test_default_pagination_is_none(self) -> None:
        a = _adapter()
        assert a._get_pagination_info() is None

    @pytest.mark.asyncio
    async def test_default_anti_bot_returns_false(self) -> None:
        a = _adapter()
        detection = AntiBotDetection(detected=True, challenge_type="captcha")
        handled = await a._handle_anti_bot(detection)
        assert handled is False

    @pytest.mark.asyncio
    async def test_default_authenticate_true(self) -> None:
        a = _adapter()
        assert await a._authenticate(MagicMock()) is True

    @pytest.mark.asyncio
    async def test_pre_post_navigation_noop(self) -> None:
        a = _adapter()
        # default implementations should be no-ops
        assert await a._pre_navigation(MagicMock(), "u") is None
        assert await a._post_navigation(MagicMock()) is None


class TestCloseBehaviour:
    @pytest.mark.asyncio
    async def test_close_when_not_started_is_noop(self) -> None:
        a = _adapter()
        a._close = AsyncMock()
        await a.close()
        # _close should not be called because _started is False
        a._close.assert_not_awaited()
        assert a.is_started is False
