"""TikTok adapter.

Browser adapter for careers.tiktok.com. Per ADR-0008, this adapter is
allowed to use Playwright with stealth flags. Restrictions: headless
required, no proxy rotation, no CAPTCHA bypass, fail fast on challenge.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from bs4 import BeautifulSoup

from job_board_scraper.adapters.protocols.browser_adapter import BrowserAdapter
from job_board_scraper.models.job import RawJobData
from job_board_scraper.utils.browser import AntiBotDetection
from job_board_scraper.utils.html_parser import parse_html

if TYPE_CHECKING:
    from playwright.async_api import Page


logger = logging.getLogger(__name__)


# Compliance status (must match manifest)
COMPLIANCE_STATUS = "needs-review"
"""Allowed by ADR-0008 — browser scraping with stealth guardrails."""


class TiktokAdapter(BrowserAdapter):
    """TikTok careers adapter using browser automation.

    Source: https://careers.tiktok.com (React SPA with Cloudflare bot challenge).
    Guardrails enforced by ADR-0008:
    - Headless only.
    - No CAPTCHA bypass.
    - Fail fast on 403 / challenge wall.
    """

    slug = "tiktok"
    SLUG = "tiktok"
    BASE_URL = "https://careers.tiktok.com"

    # Cloudflare signals we recognise as "fail fast" triggers.
    CLOUDFLARE_PATTERNS = (
        "Checking your browser",
        "Just a moment",
        "cf-challenge",
        "Attention Required",
    )

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            base_url=self.BASE_URL,
            headless=kwargs.pop("headless", True),
            navigation_timeout_ms=kwargs.pop("navigation_timeout_ms", 30000),
            **kwargs,
        )

    def _get_listing_url(self, page: int = 1) -> str:
        """Return the search URL for the given page number."""
        return f"{self.BASE_URL}/search?page={page}"

    def _parse_jobs(self, page_content: str | Any) -> list[RawJobData]:  # type: ignore[override]
        """Parse jobs from page HTML.

        Fall back to raw HTML parsing when the page is not a Playwright object.
        """
        if hasattr(page_content, "content") and callable(getattr(page_content, "content", None)):
            html = str(page_content.content())  # type: ignore[attr-defined]
        else:
            html = str(page_content)

        soup: BeautifulSoup = parse_html(html, parser="lxml")  # type: ignore[arg-type]
        jobs: list[RawJobData] = []

        # TikTok renders job cards inside <div data-job-id="..."> (best-effort).
        for card in soup.select("[data-job-id], .jobCard, article.job"):  # type: ignore[arg-type]
            title_el = card.select_one("a, h3, .job-title")
            if not title_el:
                continue
            href_raw = title_el.get("href")
            href: str | None = str(href_raw) if href_raw else None
            if not href:
                continue
            url: str = href if href.startswith("http") else f"{self.BASE_URL}{href}"
            title = title_el.get_text(strip=True)
            location_el = card.select_one(".location, .job-location")
            location = (
                location_el.get_text(strip=True) if location_el else "Singapore"
            )
            job_id_raw = card.get("data-job-id")
            jobs.append(
                RawJobData(
                    source_company_id=self.slug,
                    title=title,
                    url=url,
                    location=location,
                    source_job_id=str(job_id_raw) if job_id_raw else None,
                    raw_data={"sourced_via": "browser"},
                )
            )
        return jobs

    async def _post_navigation(self, page: Page) -> None:
        """Wait for the job card selector to appear."""
        try:
            await page.wait_for_selector(
                "[data-job-id], .jobCard, article.job",
                timeout=self._element_timeout_ms,
            )
        except Exception:  # noqa: BLE001 — selector is best-effort
            logger.debug("TikTok job-card selector not found; continuing.")

    async def _handle_anti_bot(
        self,
        detection: "AntiBotDetection",
        page: Page | None = None,
    ) -> bool:
        """Per ADR-0008, never bypass anti-bot. Log and return False."""
        logger.warning(
            "TikTok anti-bot challenge detected (%s). "
            "Per ADR-0008 we do NOT bypass. Failing fast.",
            detection.challenge_type,
        )
        return False


def is_compliance_blocked() -> bool:
    return COMPLIANCE_STATUS == "blocked-by-policy"


def get_compliance_status() -> str:
    return COMPLIANCE_STATUS
