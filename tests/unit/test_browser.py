"""Unit tests for browser utilities (utils/browser.py).

Tests cover:
- BrowserConfig validation and defaults
- BrowserManager lifecycle (start, context, close)
- Anti-bot detection logic
- Navigation helpers
- Screenshot utilities
- Custom exceptions
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from job_board_scraper.utils.browser import (
    BLOCKED_KEYWORDS,
    CLOUDFLARE_CHALLENGE_KEYWORDS,
    CLOUDFLARE_CHALLENGE_TITLES,
    AntiBotChallengeError,
    AntiBotDetection,
    BrowserConfig,
    BrowserManager,
    NavigationError,
    detect_anti_bot_challenge,
    take_screenshot,
    wait_for_element,
    wait_for_elements,
)

# ---------------------------------------------------------------------------
# BrowserConfig
# ---------------------------------------------------------------------------


class TestBrowserConfigDefaults:
    """BrowserConfig has sensible defaults."""

    def test_default_values(self) -> None:
        cfg = BrowserConfig()
        assert cfg.headless is True
        assert cfg.viewport_width == 1280
        assert cfg.viewport_height == 720
        assert cfg.locale == "en-US"
        assert cfg.timezone_id == "America/New_York"
        assert cfg.ignore_https_errors is True
        assert cfg.slow_mo == 0
        assert cfg.screenshot_dir is None
        assert cfg.navigation_timeout_ms == 30000
        assert cfg.element_timeout_ms == 10000

    def test_custom_values_are_accepted(self) -> None:
        cfg = BrowserConfig(
            headless=False,
            viewport_width=1920,
            viewport_height=1080,
            user_agent="CustomAgent/1.0",
            screenshot_dir="/tmp/screenshots",
        )
        assert cfg.headless is False
        assert cfg.viewport_width == 1920
        assert cfg.viewport_height == 1080
        assert cfg.user_agent == "CustomAgent/1.0"
        assert cfg.screenshot_dir == Path("/tmp/screenshots")

    def test_screenshot_dir_converted_to_path(self) -> None:
        cfg = BrowserConfig(screenshot_dir="/tmp/screenshots")
        assert isinstance(cfg.screenshot_dir, Path)
        assert cfg.screenshot_dir.name == "screenshots"


# ---------------------------------------------------------------------------
# AntiBotDetection
# ---------------------------------------------------------------------------


class TestAntiBotDetection:
    """AntiBotDetection dataclass behavior."""

    def test_default_values(self) -> None:
        detection = AntiBotDetection()
        assert detection.detected is False
        assert detection.challenge_type is None
        assert detection.screenshot_path is None
        assert detection.page_url is None
        assert detection.page_title is None

    def test_with_values(self) -> None:
        path = Path("/tmp/screenshot.png")
        detection = AntiBotDetection(
            detected=True,
            challenge_type="challenge",
            screenshot_path=path,
            page_url="https://example.com",
            page_title="Checking your browser",
        )
        assert detection.detected is True
        assert detection.challenge_type == "challenge"
        assert detection.screenshot_path == path


# ---------------------------------------------------------------------------
# BrowserManager lifecycle
# ---------------------------------------------------------------------------


class TestBrowserManagerLifecycle:
    """BrowserManager async context manager lifecycle."""

    @pytest.mark.asyncio
    async def test_context_manager_enters(self) -> None:
        """Manager starts browser on entry."""
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_context = AsyncMock()
        mock_playwright.chromium = MagicMock()
        mock_playwright.chromium.new_context = AsyncMock(return_value=mock_context)
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

        manager = BrowserManager()
        manager._playwright = mock_playwright

        with patch.object(
            manager, "_import_playwright", AsyncMock(return_value=mock_playwright)
        ):
            await manager._start()

        assert manager._browser is not None
        assert manager._context is not None
        assert manager._closed is False

    @pytest.mark.asyncio
    async def test_context_manager_exits(self) -> None:
        """Manager closes browser on exit."""
        mock_context = AsyncMock()
        mock_browser = MagicMock()

        manager = BrowserManager()
        manager._context = mock_context
        manager._browser = mock_browser
        manager._closed = False

        await manager._close()

        assert manager._closed is True
        mock_context.close.assert_called_once()
        mock_browser.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_double_close_is_noop(self) -> None:
        """Calling close twice is safe."""
        manager = BrowserManager()
        manager._closed = True

        # Should not raise
        await manager._close()

    @pytest.mark.asyncio
    async def test_context_property_raises_when_not_started(self) -> None:
        """Accessing context before start raises RuntimeError."""
        manager = BrowserManager()

        with pytest.raises(RuntimeError, match="not started"):
            _ = manager.context

    @pytest.mark.asyncio
    async def test_browser_property_raises_when_not_started(self) -> None:
        """Accessing browser before start raises RuntimeError."""
        manager = BrowserManager()

        with pytest.raises(RuntimeError, match="not started"):
            _ = manager.browser

    @pytest.mark.asyncio
    async def test_new_page_creates_page(self) -> None:
        """new_page creates a new page in the context."""
        mock_page = AsyncMock()
        mock_context = MagicMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)

        manager = BrowserManager()
        manager._context = mock_context

        page = await manager.new_page()
        assert page is mock_page
        mock_context.new_page.assert_called_once()


# ---------------------------------------------------------------------------
# Anti-bot detection
# ---------------------------------------------------------------------------


class TestDetectAntiBotChallenge:
    """Anti-bot challenge detection logic."""

    @pytest.mark.asyncio
    async def test_detects_cloudflare_title(self) -> None:
        """Detects 'Checking your browser' title."""
        mock_page = MagicMock()
        mock_page.url = "https://example.com"
        mock_page.title = AsyncMock(return_value="Checking your browser")
        mock_page.content = AsyncMock(
            return_value="<html><body>Please wait...</body></html>"
        )

        detection = await detect_anti_bot_challenge(mock_page)

        assert detection.detected is True
        assert detection.challenge_type == "title"
        assert detection.page_title == "Checking your browser"

    @pytest.mark.asyncio
    async def test_detects_cloudflare_content(self) -> None:
        """Detects Cloudflare keywords in content."""
        mock_page = MagicMock()
        mock_page.url = "https://example.com"
        mock_page.title = AsyncMock(return_value="Normal Page")
        mock_page.content = AsyncMock(
            return_value="<html><body>Please wait while cloudflare checks your browser</body></html>"
        )

        detection = await detect_anti_bot_challenge(mock_page)

        assert detection.detected is True
        assert detection.challenge_type == "challenge"

    @pytest.mark.asyncio
    async def test_detects_access_denied(self) -> None:
        """Detects access denied / blocked content."""
        mock_page = MagicMock()
        mock_page.url = "https://example.com"
        mock_page.title = AsyncMock(return_value="Access Denied")
        mock_page.content = AsyncMock(
            return_value="<html><body>Access Denied 403 Forbidden</body></html>"
        )

        detection = await detect_anti_bot_challenge(mock_page)

        assert detection.detected is True
        assert detection.challenge_type == "blocked"

    @pytest.mark.asyncio
    async def test_no_detection_for_normal_page(self) -> None:
        """Normal pages are not flagged."""
        mock_page = MagicMock()
        mock_page.url = "https://example.com/careers"
        mock_page.title = AsyncMock(return_value="Careers - Example")
        mock_page.content = AsyncMock(
            return_value="<html><body><h1>Join Our Team</h1></body></html>"
        )

        detection = await detect_anti_bot_challenge(mock_page)

        assert detection.detected is False
        assert detection.challenge_type is None

    @pytest.mark.asyncio
    async def test_handles_page_error_gracefully(self) -> None:
        """Page errors are logged but don't crash detection."""
        mock_page = MagicMock()
        mock_page.url = "https://example.com"
        mock_page.title = AsyncMock(side_effect=Exception("Page error"))
        mock_page.content = AsyncMock(side_effect=Exception("Page error"))

        # Should not raise, returns empty detection
        detection = await detect_anti_bot_challenge(mock_page)

        assert detection.detected is False


# ---------------------------------------------------------------------------
# Navigation helpers
# ---------------------------------------------------------------------------


class TestWaitForElement:
    """Element waiting utilities."""

    @pytest.mark.asyncio
    async def test_wait_for_element_calls_selector(self) -> None:
        """wait_for_element calls page.wait_for_selector."""
        mock_page = MagicMock()
        mock_element = MagicMock()
        mock_page.wait_for_selector = AsyncMock(return_value=mock_element)

        element = await wait_for_element(
            mock_page,
            ".job-listing",
            timeout_ms=5000,
            state="visible",
        )

        assert element is mock_element
        mock_page.wait_for_selector.assert_called_once_with(
            ".job-listing",
            timeout=5000,
            state="visible",
        )


class TestWaitForElements:
    """Multiple element waiting utilities."""

    @pytest.mark.asyncio
    async def test_wait_for_elements_queries_all(self) -> None:
        """wait_for_elements waits then queries all matching elements."""
        mock_page = MagicMock()
        mock_elements = [MagicMock(), MagicMock(), MagicMock()]
        mock_page.wait_for_selector = AsyncMock()
        mock_page.query_selector_all = AsyncMock(return_value=mock_elements)

        elements = await wait_for_elements(
            mock_page,
            ".job-card",
            timeout_ms=5000,
            min_count=2,
        )

        assert elements == mock_elements
        assert len(elements) == 3
        mock_page.wait_for_selector.assert_called_once()
        mock_page.query_selector_all.assert_called_once_with(".job-card")

    @pytest.mark.asyncio
    async def test_wait_for_elements_raises_on_insufficient(self) -> None:
        """Raises TimeoutError if not enough elements found."""
        mock_page = MagicMock()
        mock_page.wait_for_selector = AsyncMock()
        mock_page.query_selector_all = AsyncMock(return_value=[MagicMock()])  # Only 1

        with pytest.raises(TimeoutError, match="Expected at least 3"):
            await wait_for_elements(
                mock_page,
                ".job-card",
                timeout_ms=5000,
                min_count=3,
            )


# ---------------------------------------------------------------------------
# Screenshot utilities
# ---------------------------------------------------------------------------


class TestTakeScreenshot:
    """Screenshot capture utilities."""

    @pytest.mark.asyncio
    async def test_take_screenshot_calls_screenshot_method(
        self, tmp_path: Path
    ) -> None:
        """take_screenshot calls page.screenshot with correct parameters."""
        mock_page = MagicMock()
        mock_page.screenshot = AsyncMock()

        path = await take_screenshot(
            mock_page,
            tmp_path,
            prefix="test",
            full_page=True,
        )

        # Verify screenshot was called with expected parameters
        mock_page.screenshot.assert_called_once()
        call_kwargs = mock_page.screenshot.call_args.kwargs
        assert call_kwargs.get("full_page") is True
        assert "test_" in str(call_kwargs.get("path", ""))

    @pytest.mark.asyncio
    async def test_take_screenshot_creates_directory(self, tmp_path: Path) -> None:
        """take_screenshot creates output directory if needed."""
        subdir = tmp_path / "subdir" / "nested"
        mock_page = MagicMock()
        mock_page.screenshot = AsyncMock()

        await take_screenshot(mock_page, subdir, prefix="test")

        # Directory should be created
        assert subdir.exists()
        # Screenshot should be called with a path inside the directory
        call_kwargs = mock_page.screenshot.call_args.kwargs
        assert subdir in Path(call_kwargs.get("path")).parents


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class TestBrowserExceptions:
    """Browser exception hierarchy."""

    def test_browser_error_is_base(self) -> None:
        """BrowserError is the base exception."""
        from job_board_scraper.utils.browser import BrowserError

        err = BrowserError("test message")
        assert str(err) == "test message"
        assert isinstance(err, Exception)

    def test_anti_bot_challenge_error_properties(self) -> None:
        """AntiBotChallengeError carries detection metadata."""
        screenshot_path = Path("/tmp/challenge.png")
        err = AntiBotChallengeError(
            "Challenge detected",
            challenge_type="challenge",
            page_url="https://example.com",
            page_title="Checking your browser",
            screenshot_path=screenshot_path,
        )

        assert str(err) == "Challenge detected"
        assert err.challenge_type == "challenge"
        assert err.page_url == "https://example.com"
        assert err.page_title == "Checking your browser"
        assert err.screenshot_path == screenshot_path

    def test_navigation_error_wraps_cause(self) -> None:
        """NavigationError wraps the original exception."""
        original = ValueError("invalid url")
        err = NavigationError("Failed to navigate", original)

        assert str(err) == "Failed to navigate"
        assert err.__cause__ is original


# ---------------------------------------------------------------------------
# Constants verification
# ---------------------------------------------------------------------------


class TestConstants:
    """Verify anti-bot detection constants."""

    def test_cloudflare_titles_are_strings(self) -> None:
        """Cloudflare challenge titles are strings."""
        for title in CLOUDFLARE_CHALLENGE_TITLES:
            assert isinstance(title, str)
            assert len(title) > 0

    def test_cloudflare_keywords_are_strings(self) -> None:
        """Cloudflare challenge keywords are lowercase strings."""
        for keyword in CLOUDFLARE_CHALLENGE_KEYWORDS:
            assert isinstance(keyword, str)
            assert keyword.islower()

    def test_blocked_keywords_exist(self) -> None:
        """Blocked keywords includes common blocking signals."""
        assert "access denied" in BLOCKED_KEYWORDS
        assert "403" in BLOCKED_KEYWORDS
        assert "captcha" in BLOCKED_KEYWORDS
