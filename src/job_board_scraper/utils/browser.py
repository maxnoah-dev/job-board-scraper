"""Browser automation utilities using Playwright.

Provides async context managers and helpers for browser-based scraping,
including anti-bot detection, element waiting, and screenshot capture.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Page, Response


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cloudflare / anti-bot detection signals
# ---------------------------------------------------------------------------

CLOUDFLARE_CHALLENGE_TITLES = frozenset(
    {
        "Checking your browser",
        "Just a moment",
        "Cloudflare",
        "Attention Required",
    }
)

CLOUDFLARE_CHALLENGE_KEYWORDS = frozenset(
    {
        "cloudflare",
        "checking your browser",
        "please wait",
        "ray id",
        "browser check",
        "attention required",
        "ddos protection",
    }
)

BLOCKED_KEYWORDS = frozenset(
    {
        "access denied",
        "forbidden",
        "403",
        "rate limit",
        "blocked",
        "captcha",
        "reached limit",
    }
)


@dataclass
class AntiBotDetection:
    """Result of anti-bot challenge detection."""

    detected: bool = False
    challenge_type: str | None = None
    screenshot_path: Path | None = None
    page_url: str | None = None
    page_title: str | None = None


@dataclass
class BrowserConfig:
    """Configuration for browser automation.

    Attributes:
        headless: Run browser in headless mode (default True for production).
        viewport_width: Viewport width in pixels.
        viewport_height: Viewport height in pixels.
        user_agent: Custom user agent string. If None, uses Playwright default.
        locale: Browser locale (default en-US).
        timezone_id: Browser timezone (default America/New_York).
        ignore_https_errors: Ignore TLS certificate errors.
        slow_mo: Slow down operations by ms (useful for debugging).
        screenshot_dir: Directory to save failure screenshots.
        navigation_timeout_ms: Max time for page navigation.
        element_timeout_ms: Max time for element wait conditions.
    """

    headless: bool = True
    viewport_width: int = 1280
    viewport_height: int = 720
    user_agent: str | None = None
    locale: str = "en-US"
    timezone_id: str = "America/New_York"
    ignore_https_errors: bool = True
    slow_mo: int = 0
    screenshot_dir: Path | None = None
    navigation_timeout_ms: int = 30000
    element_timeout_ms: int = 10000

    def __post_init__(self) -> None:
        if self.screenshot_dir is not None:
            self.screenshot_dir = Path(self.screenshot_dir)
            self.screenshot_dir.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Browser context manager
# ---------------------------------------------------------------------------


class BrowserManager:
    """Async context manager for Playwright browser lifecycle.

    Provides a managed browser context with automatic cleanup and
    screenshot capture on failures.

    Example:
        ```python
        config = BrowserConfig(headless=True, screenshot_dir="logs/screenshots")
        async with BrowserManager(config) as manager:
            page = await manager.new_page()
            await page.goto("https://example.com")
            jobs = await page.query_selector_all(".job-listing")
        ```
    """

    def __init__(
        self,
        config: BrowserConfig | None = None,
        *,
        playwright_module: str = "playwright",
    ) -> None:
        """Initialize browser manager.

        Args:
            config: Browser configuration. Uses defaults if None.
            playwright_module: Module name to import (allows injection for testing).
        """
        self._config = config or BrowserConfig()
        self._playwright_module_name = playwright_module
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._closed = False

    async def __aenter__(self) -> BrowserManager:
        """Start browser and create context."""
        await self._start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Close browser and context."""
        await self._close()

    async def _start(self) -> None:
        """Launch browser and create context."""
        if self._closed:
            raise RuntimeError("BrowserManager already closed")

        try:
            # Import playwright
            playwright = await self._import_playwright()
            self._browser = playwright.chromium
            await self._browser.launch(
                headless=self._config.headless,
                slow_mo=self._config.slow_mo,
            )

            # Create context with stealth settings
            context_options: dict[str, Any] = {
                "viewport": {
                    "width": self._config.viewport_width,
                    "height": self._config.viewport_height,
                },
                "locale": self._config.locale,
                "timezone_id": self._config.timezone_id,
                "ignore_https_errors": self._config.ignore_https_errors,
            }

            if self._config.user_agent:
                context_options["user_agent"] = self._config.user_agent

            self._context = await self._browser.new_context(**context_options)

            # Block resource types that waste bandwidth
            await self._context.route(  # type: ignore[attr-defined]
                "**/*.{png,jpg,jpeg,gif,svg,ico,webp,woff,woff2,ttf,otf}",
                lambda route: route.abort(),
            )

            logger.debug("Browser context created successfully")

        except ImportError as e:
            raise ImportError(
                "playwright not installed. Run: pip install playwright && playwright install chromium"
            ) from e

    async def _import_playwright(self) -> Any:
        """Import playwright module (allows injection for testing)."""
        import importlib

        return importlib.import_module(self._playwright_module_name)

    async def _close(self) -> None:
        """Close browser context and browser."""
        if self._closed:
            return

        self._closed = True

        if self._context:
            try:
                await self._context.close()
            except Exception as e:
                logger.warning("Error closing browser context: %s", e)
            finally:
                self._context = None

        if self._browser:
            try:
                await self._browser.close()
            except Exception as e:
                logger.warning("Error closing browser: %s", e)
            finally:
                self._browser = None

        logger.debug("Browser closed successfully")

    @property
    def context(self) -> BrowserContext:
        """Get the browser context. Raises if not started."""
        if self._context is None:
            raise RuntimeError("BrowserManager not started or already closed")
        return self._context

    @property
    def browser(self) -> Browser:
        """Get the browser. Raises if not started."""
        if self._browser is None:
            raise RuntimeError("BrowserManager not started or already closed")
        return self._browser

    @property
    def config(self) -> BrowserConfig:
        """Get the browser configuration."""
        return self._config

    async def new_page(self) -> Page:
        """Create a new page in the context.

        Returns:
            A new Playwright Page.
        """
        return await self.context.new_page()


# ---------------------------------------------------------------------------
# Anti-bot detection
# ---------------------------------------------------------------------------


async def detect_anti_bot_challenge(page: Page) -> AntiBotDetection:
    """Detect if the page is showing an anti-bot challenge.

    Checks for common Cloudflare and anti-bot challenge signals:
    - Page titles matching known challenge pages
    - Body text containing challenge keywords
    - URL redirect patterns

    Args:
        page: Playwright Page to check.

    Returns:
        AntiBotDetection with detection results.
    """
    result = AntiBotDetection()

    try:
        result.page_url = page.url
        result.page_title = await page.title()

        # Check page title
        if result.page_title:
            title_lower = result.page_title.lower()
            for challenge_title in CLOUDFLARE_CHALLENGE_TITLES:
                if challenge_title.lower() in title_lower:
                    result.detected = True
                    result.challenge_type = "title"
                    return result

        # Check page content
        content = await page.content()
        content_lower = content.lower()

        # Check for blocked content first
        for keyword in BLOCKED_KEYWORDS:
            if keyword in content_lower:
                result.detected = True
                result.challenge_type = "blocked"
                return result

        # Check for challenge content
        for keyword in CLOUDFLARE_CHALLENGE_KEYWORDS:
            if keyword in content_lower:
                result.detected = True
                result.challenge_type = "challenge"
                return result

    except Exception as e:
        logger.warning("Error detecting anti-bot challenge: %s", e)

    return result


# ---------------------------------------------------------------------------
# Navigation helpers
# ---------------------------------------------------------------------------


async def safe_goto(
    page: Page,
    url: str,
    *,
    config: BrowserConfig | None = None,
    raise_on_challenge: bool = True,
    screenshot_on_failure: bool = True,
) -> Response | None:
    """Navigate to URL with anti-bot detection and error handling.

    Args:
        page: Playwright Page to use.
        url: URL to navigate to.
        config: Browser configuration for timeouts.
        raise_on_challenge: Raise exception if anti-bot challenge detected.
        screenshot_on_failure: Take screenshot on navigation failure.

    Returns:
        Page response if successful, None if blocked or failed.

    Raises:
        AntiBotChallengeError: If challenge detected and raise_on_challenge=True.
        NavigationError: If navigation fails.
    """
    config = config or BrowserConfig()
    result = AntiBotDetection()

    try:
        # Navigate with timeout
        response = await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=config.navigation_timeout_ms,
        )

        # Wait a bit for JS to execute
        await asyncio.sleep(1)

        # Check for anti-bot challenges
        result = await detect_anti_bot_challenge(page)

        if result.detected and raise_on_challenge:
            screenshot_path = None
            if screenshot_on_failure and config.screenshot_dir:
                screenshot_path = await take_screenshot(
                    page,
                    config.screenshot_dir,
                    prefix="challenge",
                )
                result.screenshot_path = screenshot_path

            raise AntiBotChallengeError(
                f"Anti-bot challenge detected: {result.challenge_type}",
                challenge_type=result.challenge_type,
                page_url=result.page_url,
                page_title=result.page_title,
                screenshot_path=screenshot_path,
            )

        return response

    except AntiBotChallengeError:
        raise

    except Exception as e:
        logger.error("Navigation failed for %s: %s", url, e)

        if screenshot_on_failure and config is not None and config.screenshot_dir:
            await take_screenshot(
                page,
                config.screenshot_dir,
                prefix="nav_failure",
            )

        raise NavigationError(f"Failed to navigate to {url}: {e}") from e


async def wait_for_element(
    page: Page,
    selector: str,
    *,
    timeout_ms: int = 10000,
    state: str = "visible",
) -> Any:
    """Wait for element to appear with timeout.

    Args:
        page: Playwright Page to use.
        selector: CSS selector for the element.
        timeout_ms: Max wait time in milliseconds.
        state: Wait state: "attached", "detached", "visible", "hidden".

    Returns:
        The element handle when found.

    Raises:
        TimeoutError: If element not found within timeout.
    """
    return await page.wait_for_selector(
        selector,
        timeout=timeout_ms,
        state=state,
    )


async def wait_for_elements(
    page: Page,
    selector: str,
    *,
    timeout_ms: int = 10000,
    min_count: int = 1,
) -> list[Any]:
    """Wait for multiple elements to appear.

    Args:
        page: Playwright Page to use.
        selector: CSS selector for elements.
        timeout_ms: Max wait time in milliseconds.
        min_count: Minimum number of elements expected.

    Returns:
        List of element handles.

    Raises:
        TimeoutError: If not enough elements found within timeout.
    """
    await page.wait_for_selector(
        selector,
        timeout=timeout_ms,
        state="attached",
    )

    elements = await page.query_selector_all(selector)

    if len(elements) < min_count:
        raise TimeoutError(
            f"Expected at least {min_count} elements for {selector}, found {len(elements)}"
        )

    return elements


# ---------------------------------------------------------------------------
# Screenshot utilities
# ---------------------------------------------------------------------------


async def take_screenshot(
    page: Page,
    output_dir: Path | str,
    *,
    prefix: str = "screenshot",
    full_page: bool = False,
) -> Path:
    """Take a screenshot of the current page.

    Args:
        page: Playwright Page to screenshot.
        output_dir: Directory to save screenshot.
        prefix: Filename prefix.
        full_page: Capture full scrollable page.

    Returns:
        Path to the saved screenshot.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    import datetime

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.png"
    path = output_dir / filename

    await page.screenshot(path=path, full_page=full_page)
    logger.info("Screenshot saved to %s", path)

    return path


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class BrowserError(Exception):
    """Base exception for browser operations."""

    pass


class AntiBotChallengeError(BrowserError):
    """Raised when an anti-bot challenge is detected."""

    def __init__(
        self,
        message: str,
        challenge_type: str | None = None,
        page_url: str | None = None,
        page_title: str | None = None,
        screenshot_path: Path | None = None,
    ) -> None:
        super().__init__(message)
        self.challenge_type = challenge_type
        self.page_url = page_url
        self.page_title = page_title
        self.screenshot_path = screenshot_path


class NavigationError(BrowserError):
    """Raised when page navigation fails."""

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        super().__init__(message)
        if cause is not None:
            self.__cause__ = cause
