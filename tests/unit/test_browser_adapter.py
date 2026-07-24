"""Unit tests for the browser adapter base (adapters/protocols/browser_adapter.py).

Tests cover:
- BrowserAdapter initialization
- Protocol compliance with BaseAdapter
- Lifecycle methods
- Abstract method enforcement
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from job_board_scraper.adapters.base import BaseAdapter
from job_board_scraper.adapters.protocols.browser_adapter import BrowserAdapter
from job_board_scraper.models.job import RawJobData


class StubBrowserAdapter(BrowserAdapter):
    """Minimal concrete implementation for testing."""

    SLUG = "test-browser"

    def __init__(self, **kwargs) -> None:
        super().__init__(base_url="https://example.com/careers", **kwargs)

    @property
    def slug(self) -> str:
        return self.SLUG

    def _get_listing_url(self, page: int = 1) -> str:
        return f"{self.base_url}?page={page}"

    def _parse_jobs(self, page_content: str) -> list[RawJobData]:
        return []


class TestBrowserAdapterInit:
    """BrowserAdapter initialization and configuration."""

    def test_default_config_values(self) -> None:
        adapter = StubBrowserAdapter()

        assert adapter.base_url == "https://example.com/careers"
        assert adapter.adapter_type == "browser"
        assert adapter.slug == "test-browser"
        assert adapter._navigation_timeout_ms == 30000
        assert adapter._element_timeout_ms == 10000

    def test_custom_config_values(self) -> None:
        adapter = StubBrowserAdapter(
            headless=False,
            viewport_width=1920,
            viewport_height=1080,
            screenshot_dir="/tmp/screenshots",
        )

        assert adapter._browser_config.headless is False
        assert adapter._browser_config.viewport_width == 1920
        assert adapter._browser_config.viewport_height == 1080
        assert adapter.screenshot_dir is not None
        assert "screenshots" in str(adapter.screenshot_dir)

    def test_screenshot_dir_converted_to_path(self) -> None:
        adapter = StubBrowserAdapter(screenshot_dir="/tmp/shots")
        assert str(adapter.screenshot_dir).endswith("shots")


class TestBrowserAdapterProtocol:
    """BrowserAdapter satisfies BaseAdapter protocol."""

    def test_is_base_adapter_instance(self) -> None:
        """BrowserAdapter satisfies BaseAdapter protocol."""
        adapter = StubBrowserAdapter()
        assert isinstance(adapter, BaseAdapter)

    def test_has_required_protocol_attributes(self) -> None:
        """BrowserAdapter has all required protocol attributes."""
        adapter = StubBrowserAdapter()

        # Required by BaseAdapter protocol
        assert hasattr(adapter, "slug")
        assert hasattr(adapter, "adapter_type")
        assert hasattr(adapter, "base_url")

    def test_has_required_protocol_methods(self) -> None:
        """BrowserAdapter has all required protocol methods."""
        adapter = StubBrowserAdapter()

        # Required by BaseAdapter protocol
        assert hasattr(adapter, "fetch_jobs")
        assert hasattr(adapter, "close")
        assert callable(adapter.fetch_jobs)
        assert callable(adapter.close)


class TestBrowserAdapterAbstractMethods:
    """Subclass must implement abstract methods."""

    def test_raises_without_implementation(self) -> None:
        """Class without _get_listing_url raises."""

        class IncompleteAdapter(BrowserAdapter):
            SLUG = "incomplete"

            @property
            def slug(self) -> str:
                return self.SLUG

            def __init__(self):
                super().__init__(base_url="https://example.com")

        # Abstract method not implemented
        with pytest.raises(TypeError, match="abstract"):
            adapter = IncompleteAdapter()

    def test_concrete_implementation_works(self) -> None:
        """Concrete implementation instantiates successfully."""
        adapter = StubBrowserAdapter()
        assert adapter.slug == "test-browser"
        assert adapter.adapter_type == "browser"


class TestBrowserAdapterLifecycle:
    """BrowserAdapter lifecycle methods."""

    @pytest.mark.asyncio
    async def test_close_when_not_started(self) -> None:
        """close() is safe when browser not started."""
        adapter = StubBrowserAdapter()
        adapter._started = False

        # Should not raise
        await adapter.close()

    @pytest.mark.asyncio
    async def test_close_calls_manager_close(self) -> None:
        """close() calls BrowserManager._close()."""
        adapter = StubBrowserAdapter()
        adapter._started = True
        adapter._context = AsyncMock()
        adapter._browser = MagicMock()

        with patch.object(adapter, "_close", AsyncMock()) as mock_close:
            await adapter.close()
            mock_close.assert_called_once()

        assert adapter._started is False


class TestBrowserAdapterPagination:
    """BrowserAdapter pagination methods."""

    def test_get_pagination_info_returns_none_by_default(self) -> None:
        """_get_pagination_info returns None by default."""
        adapter = StubBrowserAdapter()
        result = adapter._get_pagination_info()

        assert result is None


class TestBrowserAdapterHooks:
    """BrowserAdapter lifecycle hooks."""

    @pytest.mark.asyncio
    async def test_pre_navigation_hook_is_noop(self) -> None:
        """_pre_navigation does nothing by default."""
        adapter = StubBrowserAdapter()
        mock_page = MagicMock()

        # Should not raise
        await adapter._pre_navigation(mock_page, "https://example.com")

    @pytest.mark.asyncio
    async def test_post_navigation_hook_is_noop(self) -> None:
        """_post_navigation does nothing by default."""
        adapter = StubBrowserAdapter()
        mock_page = MagicMock()

        # Should not raise
        await adapter._post_navigation(mock_page)

    @pytest.mark.asyncio
    async def test_authenticate_returns_true_by_default(self) -> None:
        """_authenticate returns True by default."""
        adapter = StubBrowserAdapter()
        mock_page = MagicMock()

        result = await adapter._authenticate(mock_page)

        assert result is True

    @pytest.mark.asyncio
    async def test_handle_anti_bot_returns_false_by_default(self) -> None:
        """_handle_anti_bot returns False by default."""
        from job_board_scraper.utils.browser import AntiBotDetection

        adapter = StubBrowserAdapter()
        detection = AntiBotDetection(detected=True, challenge_type="challenge")

        result = await adapter._handle_anti_bot(detection)

        assert result is False


class TestBrowserAdapterListingUrl:
    """BrowserAdapter listing URL generation."""

    def test_listing_url_generation(self) -> None:
        """_get_listing_url generates correct URL."""
        adapter = StubBrowserAdapter()

        url = adapter._get_listing_url(page=1)
        assert url == "https://example.com/careers?page=1"

        url = adapter._get_listing_url(page=5)
        assert url == "https://example.com/careers?page=5"
