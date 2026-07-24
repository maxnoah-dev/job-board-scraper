"""Example HTML adapter for TechCorp (hypothetical static HTML source).

This adapter demonstrates the pattern for scraping job listings from
static HTML pages without an API/ATS integration.

Replace with actual implementation when a real HTML source is approved.
"""

from __future__ import annotations

from typing import Any

from job_board_scraper.adapters.protocols.html_adapter import (
    HtmlAdapter,
    create_job_listing_config,
)
from job_board_scraper.models.job import RawJobData
from job_board_scraper.utils.html_parser import PaginationConfig


class TechCorpAdapter(HtmlAdapter):
    """HTML adapter for TechCorp careers page.

    This adapter scrapes TechCorp's static HTML job listings page.

    Configuration:
    - Base URL: https://www.techcorp.example/careers
    - Adapter Type: HTML
    - Expected Pattern: Static HTML with job listings in a grid layout

    Example HTML structure:
    ```html
    <div class="careers-list">
        <div class="job-card">
            <h3 class="job-title">Software Engineer</h3>
            <span class="job-location">New York, NY</span>
            <a href="/careers/123" class="job-link">View Details</a>
        </div>
    </div>
    ```

    Note: This is a template implementation. Replace with actual selectors
    when TechCorp is added to the approved sources list.
    """

    slug = "techcorp"
    base_url = "https://www.techcorp.example"

    def __init__(self, **kwargs) -> None:
        """Initialize TechCorp adapter."""
        super().__init__(
            base_url=self.base_url,
            **kwargs,
        )

    def _get_listing_url(self, page: int = 1) -> str:
        """Get the job listings page URL.

        Args:
            page: Page number (1-indexed).

        Returns:
            URL for the listings page.
        """
        if page == 1:
            return f"{self._base_url}/careers"
        return f"{self._base_url}/careers?page={page}"

    def _get_job_listing_config(self):
        """Get selector configuration for TechCorp job listings.

        Returns:
            JobListingConfig with selectors for the job listing structure.
        """
        return create_job_listing_config(
            container_selector=".job-card",
            title_selector=".job-title",
            url_selector=".job-link",
            location_selector=".job-meta .location",
            url_attribute="href",
        )

    def _get_pagination_config(self) -> PaginationConfig:
        """Get pagination configuration.

        Returns:
            PaginationConfig for TechCorp's pagination style.
        """
        return PaginationConfig(
            next_button="a.next",
            page_param="page",
            max_pages=self._max_pages or 10,
            base_url=self._base_url,
        )

    def _transform_job(
        self,
        extracted_job: dict[str, Any],
        base_url: str,
    ) -> RawJobData | None:
        """Transform extracted job data to RawJobData.

        Args:
            extracted_job: Dict of extracted fields from HTML.
            base_url: Base URL for resolving relative URLs.

        Returns:
            RawJobData or None if job should be skipped.
        """
        title = extracted_job.get("title")
        url = extracted_job.get("url")

        if not title or not url:
            return None

        return RawJobData(
            source_company_id=self.slug,
            title=title,
            url=url,
            location=extracted_job.get("location") or "Remote",
            source_job_id=self._extract_job_id(url),
            date_posted=extracted_job.get("date_posted"),
            raw_data={
                "extracted_at": extracted_job.get("extracted_at"),
            },
        )

    def _extract_job_id(self, url: str) -> str | None:
        """Extract job ID from URL.

        Args:
            url: Job listing URL.

        Returns:
            Job ID string or None.
        """
        import re

        match = re.search(r"/(career|job)s?/(\d+)", url, re.IGNORECASE)
        if match:
            return match.group(2)

        match = re.search(r"job[_-]?id[=:]?(\d+)", url, re.IGNORECASE)
        if match:
            return match.group(1)

        return None
