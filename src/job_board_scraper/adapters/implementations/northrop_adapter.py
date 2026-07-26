"""Northrop Grumman adapter.

Browser adapter for northropgrumman.com/careers. Per ADR-0008, this
adapter is allowed to use Playwright with stealth flags. Restrictions:
headless required, no proxy rotation, no CAPTCHA bypass, fail fast on
challenge.
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


class NorthropAdapter(BrowserAdapter):
    """Northrop Grumman careers adapter using browser automation.

    Source: https://www.northropgrumman.com/careers (redirects to Workday SPA).
    Guardrails enforced by ADR-0008.
    """

    slug = "northrop"
    SLUG = "northrop"
    BASE_URL = "https://www.northropgrumman.com/careers"

    CLOUDFLARE_PATTERNS = (
        "Checking your browser",
        "Just a moment",
        "Cloudflare Ray ID",
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
        """Return the careers listing URL (Workday host)."""
        return f"{self.BASE_URL}?page={page}"

    def _parse_jobs(self, page_content: str | Any) -> list[RawJobData]:  # type: ignore[override]
        """Parse jobs from the Workday SPA HTML.

        Workday renders job cards inside <li data-automation-id="jobListItem"> or
        similar; we use a permissive selector list as a best-effort default.
        """
        if hasattr(page_content, "content") and callable(getattr(page_content, "content", None)):
            html = str(page_content.content())  # type: ignore[attr-defined]
        else:
            html = str(page_content)

        soup: BeautifulSoup = parse_html(html, parser="lxml")  # type: ignore[arg-type]
        jobs: list[RawJobData] = []

        for card in soup.select(  # type: ignore[arg-type]
            '[data-automation-id="jobListItem"], [data-automation-id="job"], li.job'
        ):
            title_el = card.select_one(
                '[data-automation-id="jobTitle"], a, h3'
            )
            loc_el = card.select_one(
                '[data-automation-id="jobLocation"], .location'
            )
            if not title_el:
                continue
            href_raw = title_el.get("href")
            href: str | None = str(href_raw) if href_raw else None
            if not href:
                continue
            url: str = (
                href
                if href.startswith("http")
                else f"https://www.northropgrumman.com{href}"
            )
            jobs.append(
                RawJobData(
                    source_company_id=self.slug,
                    title=title_el.get_text(strip=True),
                    url=url,
                    location=(
                        loc_el.get_text(strip=True) if loc_el else "Falls Church, VA"
                    ),
                    raw_data={"sourced_via": "browser"},
                )
            )
        return jobs

    async def _post_navigation(self, page: Page) -> None:
        """Wait for at least one Workday job-item selector to appear."""
        try:
            await page.wait_for_selector(
                '[data-automation-id="jobListItem"], [data-automation-id="job"]',
                timeout=self._element_timeout_ms,
            )
        except Exception:  # noqa: BLE001 — selector is best-effort
            logger.debug("Northrop job-list selector not found; continuing.")

    async def _handle_anti_bot(
        self,
        detection: "AntiBotDetection",
        page: Page | None = None,
    ) -> bool:
        """Per ADR-0008, never bypass anti-bot. Log and return False."""
        logger.warning(
            "Northrop anti-bot challenge detected (%s). "
            "Per ADR-0008 we do NOT bypass. Failing fast.",
            detection.challenge_type,
        )
        return False


def is_compliance_blocked() -> bool:
    return COMPLIANCE_STATUS == "blocked-by-policy"


def get_compliance_status() -> str:
    return COMPLIANCE_STATUS
