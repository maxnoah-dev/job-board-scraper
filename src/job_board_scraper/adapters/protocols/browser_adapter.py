"""Browser adapter protocol.

Concrete adapter base for sources requiring browser automation to handle
JavaScript-rendered pages, authentication flows, or anti-bot challenges.
Extends BaseAdapterImpl with Playwright integration.
"""

from __future__ import annotations

import logging
from abc import abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

from job_board_scraper.adapters.base import (
    BaseAdapterImpl,
    ExtractionResult,
    ExtractionStatus,
)
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

if TYPE_CHECKING:
    from playwright.async_api import Page


logger = logging.getLogger(__name__)


class BrowserAdapter(BrowserManager, BaseAdapterImpl):
    """Base class for browser-based adapters.

    Combines BaseAdapterImpl with BrowserManager to provide a unified
    interface for browser automation. Subclasses implement source-specific
    extraction logic while inheriting browser lifecycle management.

    Attributes:
        slug: Unique adapter identifier.
        adapter_type: Always "browser".
        base_url: Root URL for the source.

    Example:
        ```python
        class ExampleBrowserAdapter(BrowserAdapter):
            SLUG = "example"
            BASE_URL = "https://example.com/careers"

            def __init__(self, **kwargs):
                super().__init__(
                    base_url=self.BASE_URL,
                    screenshot_dir=kwargs.get("screenshot_dir"),
                    **kwargs,
                )

            async def _extract_jobs_from_page(self, page) -> list[RawJobData]:
                # Source-specific extraction logic
                ...
        ```

    Required subclass methods:
        - _get_listing_url(): URL for job listings page
        - _parse_jobs(): Parse jobs from page HTML/DOM
        - _extract_jobs_from_page(): Optional, for custom extraction flow

    Optional subclass overrides:
        - _handle_anti_bot(): Custom anti-bot handling
        - _authenticate(): Handle authentication if needed
        - _get_pagination_info(): Determine if more pages exist
    """

    def __init__(
        self,
        base_url: str,
        screenshot_dir: str | Path | None = None,
        headless: bool = True,
        navigation_timeout_ms: int = 30000,
        element_timeout_ms: int = 10000,
        user_agent: str | None = None,
        viewport_width: int = 1280,
        viewport_height: int = 720,
        slow_mo: int = 0,
        **kwargs: Any,
    ) -> None:
        """Initialize browser adapter.

        Args:
            base_url: Root URL for the source's career page.
            screenshot_dir: Directory to save failure screenshots.
            headless: Run browser in headless mode.
            navigation_timeout_ms: Max time for page navigation.
            element_timeout_ms: Max time for element wait operations.
            user_agent: Custom user agent string.
            viewport_width: Browser viewport width.
            viewport_height: Browser viewport height.
            slow_mo: Slow down operations (for debugging).
            **kwargs: Additional arguments passed to parent classes.
        """
        # Store base_url FIRST so parent class validation passes
        self._base_url = base_url
        self._navigation_timeout_ms = navigation_timeout_ms
        self._element_timeout_ms = element_timeout_ms

        # Build browser config
        self._screenshot_dir = Path(screenshot_dir) if screenshot_dir else None
        self._browser_config = BrowserConfig(
            headless=headless,
            user_agent=user_agent,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            slow_mo=slow_mo,
            screenshot_dir=self._screenshot_dir,
            navigation_timeout_ms=navigation_timeout_ms,
            element_timeout_ms=element_timeout_ms,
        )

        # Initialize BrowserManager (but don't start yet)
        BrowserManager.__init__(self, config=self._browser_config)
        BaseAdapterImpl.__init__(self)

        # Runtime state
        self._started = False
        self._current_page = None

    @property
    def adapter_type(self) -> str:
        """Adapter type is always 'browser'."""
        return "browser"

    @property
    def base_url(self) -> str:
        """Base URL for the source."""
        return self._base_url

    @property
    def screenshot_dir(self) -> Path | None:
        """Directory for failure screenshots."""
        return self._screenshot_dir

    @property
    def is_started(self) -> bool:
        """Check if browser has been started."""
        return self._started

    # ------------------------------------------------------------------------
    # Abstract methods (must be implemented by subclasses)
    # ------------------------------------------------------------------------

    @abstractmethod
    def _get_listing_url(self, page: int = 1) -> str:
        """Get the listing page URL.

        Args:
            page: Page number for pagination (1-indexed).

        Returns:
            Full URL for the listing page.
        """
        ...

    @abstractmethod
    def _parse_jobs(self, page_content: str | Any) -> list[RawJobData]:
        """Parse jobs from page content.

        Args:
            page_content: Raw HTML string or Playwright page content.

        Returns:
            List of parsed RawJobData objects.
        """
        ...

    # ------------------------------------------------------------------------
    # Optional methods (can be overridden by subclasses)
    # ------------------------------------------------------------------------

    def _get_pagination_info(self, page: Page | None = None) -> dict[str, Any] | None:
        """Get pagination info from current page.

        Override this if the source has custom pagination logic.

        Args:
            page: Playwright page object (if available).

        Returns:
            Dict with 'has_next', 'current_page', 'total_pages', etc.
            None if pagination is not supported.
        """
        return None

    async def _handle_anti_bot(
        self,
        detection: AntiBotDetection,
        page: Page | None = None,
    ) -> bool:
        """Handle detected anti-bot challenge.

        Default behavior logs and returns False (challenge not handled).
        Override to implement custom challenge handling.

        Args:
            detection: Anti-bot detection result.
            page: Playwright page (if available).

        Returns:
            True if challenge was successfully handled, False otherwise.
        """
        logger = logging.getLogger(f"{__name__}.{self.slug}")
        logger.warning(
            "Anti-bot challenge detected (type=%s) for %s",
            detection.challenge_type,
            self.slug,
        )
        return False

    async def _authenticate(self, page: Page) -> bool:
        """Perform authentication if required.

        Override this if the source requires login.

        Args:
            page: Playwright page for authentication.

        Returns:
            True if authenticated successfully, False otherwise.
        """
        return True

    async def _pre_navigation(self, page: Page, url: str) -> None:
        """Hook called before navigating to a URL.

        Override for custom pre-navigation actions (e.g., cookie consent).

        Args:
            page: Playwright page.
            url: URL being navigated to.
        """
        pass

    async def _post_navigation(self, page: Page) -> None:
        """Hook called after successful navigation.

        Override for custom post-navigation actions (e.g., wait for specific elements).

        Args:
            page: Playwright page after navigation.
        """
        pass

    # ------------------------------------------------------------------------
    # Lifecycle methods
    # ------------------------------------------------------------------------

    async def fetch_jobs(self) -> ExtractionResult:
        """Fetch all jobs from the source using browser automation.

        Default implementation:
        1. Start browser if not started
        2. Create new page
        3. Navigate to listing URL
        4. Wait for job elements
        5. Parse jobs from page
        6. Handle pagination
        7. Return results

        Returns:
            ExtractionResult with all jobs found.
        """
        all_jobs: list[RawJobData] = []
        warnings: list[str] = []
        pages_fetched = 0
        requests_made = 0
        page_num = 1
        max_pages = 10  # Safety limit

        try:
            # Start browser if needed
            if not self._started:
                await self._start()
                self._started = True

            # Create page for extraction
            page = await self.new_page()

            while page_num <= max_pages:
                listing_url = self._get_listing_url(page=page_num)

                try:
                    # Pre-navigation hook
                    await self._pre_navigation(page, listing_url)

                    # Navigate to listing page
                    response = await safe_goto(
                        page,
                        listing_url,
                        config=self._browser_config,
                        raise_on_challenge=False,  # We handle it ourselves
                    )

                    if response is None:
                        warnings.append(f"Failed to load page {page_num}")
                        break

                    requests_made += 1

                    # Check for anti-bot challenge
                    detection = await detect_anti_bot_challenge(page)
                    if detection.detected:
                        handled = await self._handle_anti_bot(detection, page)
                        if not handled:
                            warnings.append(
                                f"Anti-bot challenge on page {page_num}: {detection.challenge_type}"
                            )
                            # Take screenshot for debugging
                            if self._screenshot_dir:
                                await take_screenshot(
                                    page,
                                    self._screenshot_dir,
                                    prefix=f"{self.slug}_challenge",
                                )
                            break

                    # Post-navigation hook
                    await self._post_navigation(page)

                    pages_fetched += 1

                    # Parse jobs from page
                    content = await page.content()
                    jobs = self._parse_jobs(content)
                    all_jobs.extend(jobs)

                    # Check pagination
                    pagination = self._get_pagination_info(page)
                    if pagination is None or not pagination.get("has_next", False):
                        break

                    page_num += 1

                except AntiBotChallengeError as e:
                    warnings.append(f"Anti-bot challenge: {e}")
                    if self._screenshot_dir:
                        await take_screenshot(
                            page,
                            self._screenshot_dir,
                            prefix=f"{self.slug}_challenge",
                        )
                    break

                except NavigationError as e:
                    warnings.append(f"Navigation error on page {page_num}: {e}")
                    if self._screenshot_dir:
                        await take_screenshot(
                            page,
                            self._screenshot_dir,
                            prefix=f"{self.slug}_nav_error",
                        )
                    break

                except Exception as e:
                    warnings.append(f"Error on page {page_num}: {str(e)}")
                    logger.exception("Error fetching page %d", page_num)
                    if self._screenshot_dir:
                        await take_screenshot(
                            page,
                            self._screenshot_dir,
                            prefix=f"{self.slug}_error",
                        )
                    break

            # Close page
            await page.close()

        except Exception as e:
            return ExtractionResult(
                jobs=all_jobs,
                status=ExtractionStatus.FAILED,
                error=f"Browser extraction failed: {str(e)}",
                warnings=warnings,
                pages_fetched=pages_fetched,
                requests_made=requests_made,
            )

        finally:
            # Cleanup
            if self._started:
                await self._close()
                self._started = False

        # Determine status
        if not all_jobs and warnings:
            status = (
                ExtractionStatus.FAILED
                if any("challenge" in w or "blocked" in w for w in warnings)
                else ExtractionStatus.PARTIAL
            )
        elif warnings:
            status = ExtractionStatus.PARTIAL
        else:
            status = ExtractionStatus.SUCCESS

        return ExtractionResult(
            jobs=all_jobs,
            status=status,
            warnings=warnings,
            pages_fetched=pages_fetched,
            requests_made=requests_made,
        )

    async def close(self) -> None:
        """Close browser and release resources."""
        if self._started:
            await self._close()
            self._started = False
