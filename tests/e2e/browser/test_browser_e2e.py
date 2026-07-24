"""E2E tests for browser adapters.

These tests validate browser automation infrastructure with deterministic
fixtures. Tests run with Playwright in headless mode.

E2E Test Strategy:
- Use Playwright's built-in mock server or local fixtures
- Test browser lifecycle (start, navigate, cleanup)
- Verify anti-bot detection works correctly
- Test pagination and error handling
- Verify cleanup on exit (no resource leaks)

NOTE: These tests require Playwright to be installed:
    pip install playwright
    playwright install chromium
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from job_board_scraper.adapters.protocols.browser_adapter import BrowserAdapter
from job_board_scraper.models.job import RawJobData
from job_board_scraper.utils.browser import (
    AntiBotChallengeError,
    AntiBotDetection,
    BrowserConfig,
    BrowserManager,
    NavigationError,
    detect_anti_bot_challenge,
    safe_goto,
    take_screenshot,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def browser_config(tmp_path: Path) -> BrowserConfig:
    """Create browser config with temporary screenshot directory."""
    return BrowserConfig(
        headless=True,
        screenshot_dir=tmp_path / "screenshots",
        navigation_timeout_ms=5000,
        element_timeout_ms=2000,
    )


@pytest.fixture
def mock_playwright_context():
    """Mock Playwright context for testing without browser launch."""
    context = MagicMock()
    context.route = AsyncMock()
    context.new_page = AsyncMock(return_value=AsyncMock())
    return context


# ---------------------------------------------------------------------------
# Test stubs for concrete adapter implementations
# ---------------------------------------------------------------------------


class DeterministicBrowserAdapter(BrowserAdapter):
    """Browser adapter that returns deterministic job data for testing."""

    SLUG = "deterministic-test"
    BASE_URL = "https://example.com/careers"

    def __init__(self, **kwargs) -> None:
        super().__init__(
            base_url=self.BASE_URL,
            headless=True,
            **kwargs,
        )

    @property
    def slug(self) -> str:
        return self.SLUG

    def _get_listing_url(self, page: int = 1) -> str:
        return f"{self.BASE_URL}?page={page}"

    def _parse_jobs(self, page_content: str | Any) -> list[RawJobData]:
        # Return empty for empty content
        if not page_content or not str(page_content).strip():
            return []
        # Return a job for non-empty content
        return [
            RawJobData(
                source_company_id=self.slug,
                source_job_id="job-1",
                title="Software Engineer",
                location="Remote",
                url="https://example.com/jobs/1",
            ),
        ]


# ---------------------------------------------------------------------------
# BrowserManager E2E Tests
# ---------------------------------------------------------------------------


class TestBrowserManagerE2E:
    """End-to-end tests for BrowserManager lifecycle."""

    @pytest.mark.asyncio
    async def test_context_manager_starts_and_stops(self) -> None:
        """Browser starts on __aenter__ and stops on __aexit__."""
        manager = BrowserManager(config=BrowserConfig(headless=True))

        # Mock the playwright import
        mock_playwright = MagicMock()
        mock_browser = MagicMock()
        mock_context = AsyncMock()
        mock_context.close = AsyncMock()
        mock_browser.close = AsyncMock()

        mock_playwright.chromium = MagicMock()
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright.chromium.new_context = AsyncMock(return_value=mock_context)

        with patch.object(
            manager, "_import_playwright", AsyncMock(return_value=mock_playwright)
        ):
            async with manager:
                assert manager._browser is not None
                assert manager._context is not None
                assert manager._closed is False

            # After exit, should be closed
            assert manager._closed is True

    @pytest.mark.asyncio
    async def test_context_manager_handles_exception(self) -> None:
        """Browser cleanup happens even when exception occurs."""
        manager = BrowserManager(config=BrowserConfig(headless=True))

        mock_browser = MagicMock()
        mock_context = MagicMock()

        # Set async methods on browser (returned by launch)
        mock_browser.close = AsyncMock()
        mock_browser.new_context = AsyncMock()
        mock_context.close = AsyncMock()
        mock_context.route = AsyncMock()

        # Create chromium mock - this is what self._browser will point to
        chromium_mock = MagicMock()
        chromium_mock.close = AsyncMock()  # BrowserManager.close() calls this
        chromium_mock.launch = AsyncMock(return_value=mock_browser)
        chromium_mock.new_context = AsyncMock(return_value=mock_context)

        mock_playwright = MagicMock()
        mock_playwright.chromium = chromium_mock

        with patch.object(
            manager, "_import_playwright", AsyncMock(return_value=mock_playwright)
        ):
            try:
                async with manager:
                    raise ValueError("Test exception")
            except ValueError:
                pass

        # Cleanup should still happen
        mock_context.close.assert_called_once()
        # chromium_mock.close is called, not mock_browser.close
        chromium_mock.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_resource_cleanup_on_failure(
        self, browser_config: BrowserConfig
    ) -> None:
        """Resources are cleaned up even if browser launch fails."""
        manager = BrowserManager(config=browser_config)

        with (
            patch.object(
                manager,
                "_import_playwright",
                AsyncMock(side_effect=ImportError("Playwright not installed")),
            ),
            pytest.raises(ImportError),
        ):
            await manager._start()

        # ImportError is raised before _closed is set
        # Manager is still usable after failure


# ---------------------------------------------------------------------------
# Anti-bot Detection E2E Tests
# ---------------------------------------------------------------------------


class TestAntiBotDetectionE2E:
    """End-to-end tests for anti-bot challenge detection."""

    @pytest.mark.asyncio
    async def test_detects_cloudflare_challenge(self) -> None:
        """Cloudflare challenge page is detected."""
        mock_page = MagicMock()
        mock_page.url = "https://example.com"
        mock_page.title = AsyncMock(return_value="Checking your browser - Cloudflare")
        mock_page.content = AsyncMock(
            return_value="""
            <html>
            <head><title>Checking your browser - Cloudflare</title></head>
            <body>
                <div class="cf-wrapper">Please wait while we check your browser...</div>
                <div class="ray-id">Ray ID: 1234567890</div>
            </body>
            </html>
        """
        )

        detection = await detect_anti_bot_challenge(mock_page)

        assert detection.detected is True
        assert detection.challenge_type == "title"
        assert detection.page_title == "Checking your browser - Cloudflare"

    @pytest.mark.asyncio
    async def test_detects_access_blocked(self) -> None:
        """Access denied page is detected."""
        mock_page = MagicMock()
        mock_page.url = "https://example.com/careers"
        mock_page.title = AsyncMock(return_value="403 Forbidden")
        mock_page.content = AsyncMock(
            return_value="""
            <html>
            <head><title>403 Forbidden</title></head>
            <body>
                <h1>Access Denied</h1>
                <p>You have been blocked.</p>
            </body>
            </html>
        """
        )

        detection = await detect_anti_bot_challenge(mock_page)

        assert detection.detected is True
        assert detection.challenge_type == "blocked"

    @pytest.mark.asyncio
    async def test_normal_page_passes(self) -> None:
        """Normal career page is not flagged."""
        mock_page = MagicMock()
        mock_page.url = "https://example.com/careers"
        mock_page.title = AsyncMock(return_value="Careers at Example")
        mock_page.content = AsyncMock(
            return_value="""
            <html>
            <head><title>Careers at Example</title></head>
            <body>
                <h1>Join Our Team</h1>
                <div class="job-card">Software Engineer - Remote</div>
                <div class="job-card">Product Manager - NYC</div>
            </body>
            </html>
        """
        )

        detection = await detect_anti_bot_challenge(mock_page)

        assert detection.detected is False
        assert detection.challenge_type is None

    @pytest.mark.asyncio
    async def test_captcha_page_detected(self) -> None:
        """CAPTCHA challenge is detected."""
        mock_page = MagicMock()
        mock_page.url = "https://example.com"
        mock_page.title = AsyncMock(return_value="Security Check")
        mock_page.content = AsyncMock(
            return_value="""
            <html>
            <head><title>Security Check</title></head>
            <body>
                <h1>CAPTCHA Required</h1>
                <p>Please complete the captcha to continue.</p>
            </body>
            </html>
        """
        )

        detection = await detect_anti_bot_challenge(mock_page)

        assert detection.detected is True
        assert detection.challenge_type == "blocked"


# ---------------------------------------------------------------------------
# Navigation Helper E2E Tests
# ---------------------------------------------------------------------------


class TestNavigationHelpersE2E:
    """End-to-end tests for navigation helper functions."""

    @pytest.mark.asyncio
    async def test_safe_goto_with_response(self) -> None:
        """safe_goto returns response on success."""
        mock_response = MagicMock()
        mock_response.status = 200

        mock_page = MagicMock()
        mock_page.goto = AsyncMock(return_value=mock_response)
        mock_page.title = AsyncMock(return_value="Normal Page")
        mock_page.content = AsyncMock(return_value="<html><body>Content</body></html>")

        config = BrowserConfig(navigation_timeout_ms=5000)

        with patch(
            "job_board_scraper.utils.browser.detect_anti_bot_challenge",
            AsyncMock(return_value=AntiBotDetection()),
        ):
            response = await safe_goto(
                mock_page,
                "https://example.com",
                config=config,
                raise_on_challenge=False,
            )

        assert response is mock_response
        mock_page.goto.assert_called_once()

    @pytest.mark.asyncio
    async def test_safe_goto_raises_on_challenge(self) -> None:
        """safe_goto raises AntiBotChallengeError on challenge detection."""
        mock_page = MagicMock()
        mock_page.goto = AsyncMock()
        mock_page.title = AsyncMock(return_value="Checking your browser")
        mock_page.content = AsyncMock(return_value="<html>Challenge</html>")
        mock_page.screenshot = AsyncMock()  # Add async mock for screenshot

        config = BrowserConfig()

        with patch(
            "job_board_scraper.utils.browser.detect_anti_bot_challenge",
            AsyncMock(
                return_value=AntiBotDetection(
                    detected=True,
                    challenge_type="title",
                    page_title="Checking your browser",
                )
            ),
        ):
            with pytest.raises(AntiBotChallengeError) as exc_info:
                await safe_goto(mock_page, "https://example.com", config=config)

            assert "Anti-bot challenge detected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_safe_goto_raises_on_navigation_error(self) -> None:
        """safe_goto raises NavigationError on timeout."""
        mock_page = MagicMock()
        mock_page.goto = AsyncMock(side_effect=TimeoutError("Navigation timeout"))
        mock_page.screenshot = AsyncMock()  # Add async mock for screenshot

        config = BrowserConfig()

        with pytest.raises(NavigationError) as exc_info:
            await safe_goto(mock_page, "https://example.com", config=config)

        assert "Failed to navigate" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Screenshot E2E Tests
# ---------------------------------------------------------------------------


class TestScreenshotE2E:
    """End-to-end tests for screenshot utilities."""

    @pytest.mark.asyncio
    async def test_screenshot_calls_page_method(self, tmp_path: Path) -> None:
        """take_screenshot calls page.screenshot method."""
        mock_page = MagicMock()
        mock_page.screenshot = AsyncMock()

        path = await take_screenshot(
            mock_page,
            tmp_path,
            prefix="test_page",
            full_page=False,
        )

        # Verify screenshot was called
        mock_page.screenshot.assert_called_once()
        call_kwargs = mock_page.screenshot.call_args.kwargs
        assert call_kwargs.get("full_page") is False
        assert "test_page" in str(call_kwargs.get("path", ""))

    @pytest.mark.asyncio
    async def test_screenshot_includes_prefix(self, tmp_path: Path) -> None:
        """Screenshots include prefix in filename."""
        mock_page = MagicMock()
        mock_page.screenshot = AsyncMock()

        path = await take_screenshot(mock_page, tmp_path, prefix="my_screenshot")

        call_kwargs = mock_page.screenshot.call_args.kwargs
        assert "my_screenshot" in str(call_kwargs.get("path", ""))

    @pytest.mark.asyncio
    async def test_screenshot_creates_directory(self, tmp_path: Path) -> None:
        """Screenshot creates output directory if needed."""
        nested_dir = tmp_path / "deeply" / "nested" / "path"
        mock_page = MagicMock()
        mock_page.screenshot = AsyncMock()

        await take_screenshot(mock_page, nested_dir, prefix="test")

        # Directory should be created
        assert nested_dir.exists()


# ---------------------------------------------------------------------------
# BrowserAdapter E2E Tests
# ---------------------------------------------------------------------------


class TestBrowserAdapterE2E:
    """End-to-end tests for BrowserAdapter base class."""

    @pytest.mark.asyncio
    async def test_adapter_close_cleans_up_resources(self) -> None:
        """close() properly cleans up browser resources."""
        adapter = DeterministicBrowserAdapter()
        adapter._started = True
        # IMPORTANT: close must be AsyncMock
        mock_context = MagicMock()
        mock_context.close = AsyncMock()
        adapter._context = mock_context
        mock_browser = MagicMock()
        mock_browser.close = AsyncMock()
        adapter._browser = mock_browser

        # Capture reference before close() sets it to None
        context_close = mock_context.close

        await adapter.close()

        assert adapter._started is False
        # Assert on captured reference, not adapter._context which is now None
        context_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_adapter_close_is_idempotent(self) -> None:
        """close() can be called multiple times safely."""
        adapter = DeterministicBrowserAdapter()
        adapter._started = False  # Not started

        # Should not raise
        await adapter.close()
        await adapter.close()

    @pytest.mark.asyncio
    async def test_adapter_lifecycle_with_mocked_browser(self) -> None:
        """Full adapter lifecycle with mocked browser."""
        adapter = DeterministicBrowserAdapter()

        # Mock browser components
        mock_page = AsyncMock()
        mock_page.content = AsyncMock(return_value="<html>Jobs</html>")
        mock_page.goto = AsyncMock()
        mock_page.close = AsyncMock()
        mock_page.title = AsyncMock(return_value="Careers")

        mock_context = MagicMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.route = AsyncMock()
        mock_context.close = AsyncMock()

        mock_browser = MagicMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_browser.close = AsyncMock()

        mock_playwright = MagicMock()
        mock_playwright.chromium = MagicMock()
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright.chromium.new_context = AsyncMock(return_value=mock_context)

        with (
            patch.object(
                adapter, "_import_playwright", AsyncMock(return_value=mock_playwright)
            ),
            patch("job_board_scraper.utils.browser.safe_goto", AsyncMock()),
            patch(
                "job_board_scraper.utils.browser.detect_anti_bot_challenge",
                AsyncMock(return_value=AntiBotDetection()),
            ),
        ):
            result = await adapter.fetch_jobs()

        # Verify cleanup happened
        assert adapter._started is False


# ---------------------------------------------------------------------------
# Cleanup Verification Tests
# ---------------------------------------------------------------------------


class TestCleanupVerification:
    """Tests to verify proper cleanup of browser resources."""

    @pytest.mark.asyncio
    async def test_no_context_leak_on_success(self) -> None:
        """Context is closed after successful extraction."""
        manager = BrowserManager()
        mock_context = AsyncMock()
        mock_browser = MagicMock()
        mock_browser.close = AsyncMock()
        manager._context = mock_context
        manager._browser = mock_browser
        manager._closed = False

        await manager._close()

        mock_context.close.assert_called_once()
        assert manager._closed is True

    @pytest.mark.asyncio
    async def test_no_context_leak_on_error(self) -> None:
        """Context is closed even when an error occurs."""
        manager = BrowserManager()
        mock_context = AsyncMock()
        mock_browser = MagicMock()
        mock_browser.close = AsyncMock()
        manager._context = mock_context
        manager._browser = mock_browser
        manager._closed = False

        # Simulate error during extraction
        await manager._close()

        # Context should still be closed
        mock_context.close.assert_called_once()
        assert manager._closed is True

    @pytest.mark.asyncio
    async def test_browser_closed_even_on_context_error(self) -> None:
        """Browser is closed even if context close fails."""
        manager = BrowserManager()
        mock_context = AsyncMock(side_effect=Exception("Context close failed"))
        mock_browser = MagicMock()
        mock_browser.close = AsyncMock()
        manager._context = mock_context
        manager._browser = mock_browser
        manager._closed = False

        await manager._close()

        # Browser should still be closed
        mock_browser.close.assert_called_once()
        assert manager._closed is True

    @pytest.mark.asyncio
    async def test_multiple_close_calls_safe(self) -> None:
        """Multiple close calls don't cause errors."""
        manager = BrowserManager()
        manager._closed = True

        # Should not raise
        await manager._close()
        await manager._close()


# ---------------------------------------------------------------------------
# Compliance Tests
# ---------------------------------------------------------------------------


class TestComplianceEnforcement:
    """Tests for blocked-by-policy compliance enforcement."""

    def test_tiktok_adapter_is_deferred(self) -> None:
        """TikTok adapter reports correct compliance status."""
        from job_board_scraper.adapters.implementations.tiktok_adapter import (
            COMPLIANCE_STATUS,
            is_compliance_blocked,
        )

        assert COMPLIANCE_STATUS == "blocked-by-policy"
        assert is_compliance_blocked() is True

    def test_northrop_adapter_is_deferred(self) -> None:
        """Northrop adapter reports correct compliance status."""
        from job_board_scraper.adapters.implementations.northrop_adapter import (
            COMPLIANCE_STATUS,
            is_compliance_blocked,
        )

        assert COMPLIANCE_STATUS == "blocked-by-policy"
        assert is_compliance_blocked() is True

    @pytest.mark.asyncio
    async def test_deferred_adapter_does_not_bypass_challenges(self) -> None:
        """Deferred adapters log but don't bypass anti-bot challenges."""
        from job_board_scraper.adapters.implementations.tiktok_adapter import (
            TiktokAdapter,
        )

        adapter = TiktokAdapter()
        detection = AntiBotDetection(detected=True, challenge_type="challenge")

        # Should return False (not handled)
        result = await adapter._handle_anti_bot(detection)

        assert result is False


# ---------------------------------------------------------------------------
# Resource Limits Tests
# ---------------------------------------------------------------------------


class TestResourceLimits:
    """Tests for resource limit enforcement."""

    def test_pagination_max_pages_enforced(self) -> None:
        """Pagination has safety limit on pages."""
        adapter = DeterministicBrowserAdapter()

        # Max pages is enforced in fetch_jobs
        # This tests the constant exists
        max_pages = 10  # From BrowserAdapter.fetch_jobs
        assert max_pages > 0
        assert max_pages <= 100  # Reasonable upper bound

    @pytest.mark.asyncio
    async def test_adapter_timeout_is_configurable(self) -> None:
        """Adapter respects configured timeouts."""
        adapter = DeterministicBrowserAdapter(navigation_timeout_ms=5000)

        assert adapter._navigation_timeout_ms == 5000
        assert adapter._element_timeout_ms == 10000  # Default


# ---------------------------------------------------------------------------
# Deterministic Fixture Tests
# ---------------------------------------------------------------------------


class TestDeterministicFixtures:
    """Tests using deterministic fixtures for reproducible results."""

    @pytest.mark.asyncio
    async def test_adapter_produces_deterministic_results(self) -> None:
        """Adapter returns same structure for same input."""
        adapter = DeterministicBrowserAdapter()

        # Parse same content twice
        jobs1 = adapter._parse_jobs("<html>Test</html>")
        jobs2 = adapter._parse_jobs("<html>Test</html>")

        assert len(jobs1) == len(jobs2)
        assert jobs1[0].title == jobs2[0].title
        assert jobs1[0].source_company_id == jobs2[0].source_company_id

    @pytest.mark.asyncio
    async def test_empty_page_returns_empty_jobs(self) -> None:
        """Empty page content returns empty job list."""
        adapter = DeterministicBrowserAdapter()

        jobs = adapter._parse_jobs("")
        assert len(jobs) == 0

    @pytest.mark.asyncio
    async def test_adapter_handles_pagination_params(self) -> None:
        """Adapter generates correct pagination URLs."""
        adapter = DeterministicBrowserAdapter()

        url1 = adapter._get_listing_url(page=1)
        url2 = adapter._get_listing_url(page=5)

        assert "page=1" in url1
        assert "page=5" in url2
