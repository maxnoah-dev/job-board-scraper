"""TikTok adapter (DEFERRED).

Browser adapter for careers.tiktok.com.

STATUS: blocked-by-policy per ADR-0007 and docs/sources/compliance-notes.md.

This adapter is scaffolded and ready for implementation once:
1. Compliance status is updated to 'approved' in the manifest
2. Product owner provides explicit sign-off
3. A legal/compliance path is established (data-sharing agreement or similar)

Until then, this adapter will NOT be loaded by the registry even if enabled
in config. See AdapterRegistry behavior for blocked sources.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from job_board_scraper.adapters.protocols.browser_adapter import BrowserAdapter
from job_board_scraper.models.job import RawJobData

if TYPE_CHECKING:
    from playwright.async_api import Page


# Compliance status (must match manifest)
COMPLIANCE_STATUS = "blocked-by-policy"
"""This source is blocked per ADR-0007 compliance policy."""


class TiktokAdapter(BrowserAdapter):
    """TikTok careers adapter using browser automation.

    STATUS: DEFERRED - See COMPLIANCE_STATUS above.

    This adapter requires:
    - Browser automation to handle JavaScript-rendered career SPA
    - Anti-bot detection and handling (Cloudflare-style challenges)
    - Pagination through job listings
    - Optional authentication if required

    Expected job board structure (from initial analysis):
    - URL pattern: https://careers.tiktok.com/search?job_type=campus
    - Job cards: CSS selector to be determined
    - Fields: title, location, job_id, posting_date, url

    Implementation notes when unblocked:
    - TikTok uses a React SPA with dynamic content loading
    - May require waiting for API calls to complete
    - Rate limiting is strictly enforced
    - CAPTCHA may appear under heavy load
    """

    SLUG = "tiktok"
    BASE_URL = "https://careers.tiktok.com"

    # Known challenge patterns
    CLOUDFLARE_PATTERNS = [
        "Checking your browser",
        "Just a moment",
        "cf-challenge",
    ]

    def __init__(self, **kwargs) -> None:
        """Initialize TikTok adapter.

        Args:
            **kwargs: Arguments passed to BrowserAdapter.
        """
        super().__init__(
            base_url=self.BASE_URL,
            **kwargs,
        )

    @property
    def slug(self) -> str:
        return self.SLUG

    def _get_listing_url(self, page: int = 1) -> str:
        """Get the job listings URL.

        Args:
            page: Page number for pagination.

        Returns:
            Full URL for the listing page.
        """
        # Placeholder URL structure - to be confirmed when unblocked
        return f"{self.BASE_URL}/search?page={page}"

    def _parse_jobs(self, page_content: str | Any) -> list[RawJobData]:
        """Parse jobs from page content.

        NOTE: This is a placeholder. Actual implementation requires:
        - DOM parsing with Playwright selectors
        - Anti-bot evasion handling
        - Dynamic content waiting

        Args:
            page_content: Raw HTML or page object.

        Returns:
            Empty list until implementation is unblocked.
        """
        # Return empty until unblocked
        return []

    async def _handle_anti_bot(
        self,
        detection: BrowserAdapter.AntiBotDetection,
        page: Page | None = None,
    ) -> bool:
        """Handle anti-bot challenge.

        NOTE: Per ADR-0007, we do NOT implement anti-bot bypass.
        This method logs the detection and returns False.

        Args:
            detection: Anti-bot detection result.
            page: Playwright page.

        Returns:
            False (challenge not handled - as required by policy).
        """
        import logging

        logger = logging.getLogger(f"{__name__}.{self.slug}")

        logger.warning(
            "TikTok anti-bot challenge detected (type=%s). "
            "Per ADR-0007, we do not implement bypass. "
            "Source is compliance-blocked until product owner sign-off.",
            detection.challenge_type,
        )
        return False


# ---------------------------------------------------------------------------
# Module-level compliance check
# ---------------------------------------------------------------------------


def is_compliance_blocked() -> bool:
    """Check if this adapter is blocked by compliance policy.

    Returns:
        True if source is blocked-by-policy per manifest.
    """
    return COMPLIANCE_STATUS == "blocked-by-policy"


def get_compliance_status() -> str:
    """Get the current compliance status.

    Returns:
        Compliance status string.
    """
    return COMPLIANCE_STATUS
