"""Example HTML adapter for StartupXYZ (hypothetical static HTML source).

This adapter demonstrates an alternative HTML scraping pattern using
a different page structure (list-based instead of card-based).
"""

from __future__ import annotations

from typing import Any

from job_board_scraper.adapters.protocols.html_adapter import (
    HtmlAdapter,
    create_job_listing_config,
)
from job_board_scraper.models.job import RawJobData
from job_board_scraper.utils.html_parser import PaginationConfig


class StartupXYZAdapter(HtmlAdapter):
    """HTML adapter for StartupXYZ careers page.

    This adapter scrapes StartupXYZ's static HTML job listings page
    which uses a list-based layout instead of card grid.

    Configuration:
    - Base URL: https://startupxyz.example.com
    - Adapter Type: HTML
    - Expected Pattern: Table/list-based job listings

    Example HTML structure:
    ```html
    <table class="jobs-table">
        <tbody>
            <tr class="job-row" data-job-id="456">
                <td class="job-title-cell">
                    <a href="/jobs/456">Senior Developer</a>
                </td>
                <td class="job-location-cell">San Francisco</td>
                <td class="job-date-cell">July 2026</td>
            </tr>
        </tbody>
    </table>
    <div class="pagination">
        <a href="/jobs?page=2">Next</a>
    </div>
    ```

    Note: This is a template implementation. Replace with actual selectors
    when StartupXYZ is added to the approved sources list.
    """

    slug = "startupxyz"
    base_url = "https://startupxyz.example.com"

    def __init__(self, **kwargs) -> None:
        """Initialize StartupXYZ adapter."""
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
            return f"{self._base_url}/jobs"
        return f"{self._base_url}/jobs?page={page}"

    def _get_job_listing_config(self):
        """Get selector configuration for StartupXYZ job listings.

        Returns:
            JobListingConfig with selectors for the list-based layout.
        """
        return create_job_listing_config(
            container_selector=".job-row",
            title_selector="a",
            url_selector="a",
            location_selector=".job-location-cell",
            url_attribute="href",
        )

    def _get_pagination_config(self) -> PaginationConfig:
        """Get pagination configuration.

        Returns:
            PaginationConfig for StartupXYZ's pagination style.
        """
        return PaginationConfig(
            next_button="a.next",
            page_param="page",
            max_pages=self._max_pages or 20,
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

        match = re.search(r"/jobs/(\d+)", url)
        if match:
            return match.group(1)

        match = re.search(r"id[=:]?(\d+)", url, re.IGNORECASE)
        if match:
            return match.group(1)

        return None
