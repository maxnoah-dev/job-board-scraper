"""HTML adapter protocol.

Concrete adapter base for sources that expose static HTML pages
with job listings. Used for companies that don't have an API/ATS
integration.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any

import httpx

from job_board_scraper.adapters.base import BaseAdapterImpl, ExtractionResult
from job_board_scraper.models.job import RawJobData
from job_board_scraper.utils.html_parser import (
    JobListingConfig,
    PaginationConfig,
    extract_all_jobs,
    find_next_page_url,
    parse_date_string,
    parse_html,
    should_continue_pagination,
)

if TYPE_CHECKING:
    from job_board_scraper.utils.rate_limiter import RateLimiter


class HtmlAdapter(BaseAdapterImpl):
    """Base class for HTML scraping adapters.

    Provides common utilities for extracting job listings from static HTML pages:
    - HTTP client with timeout and retries
    - Rate limiting
    - Pagination handling
    - BeautifulSoup-based parsing
    - Configurable selectors for different page structures

    Subclasses must implement:
    - _get_listing_url() - URL for job listings page
    - _get_job_listing_config() - Selector configuration for extracting jobs
    - _transform_job() - Transform extracted job data to RawJobData format

    Optional overrides:
    - _get_pagination_config() - Pagination configuration
    - _should_scrape_page() - Decide whether to scrape a specific page
    """

    def __init__(
        self,
        base_url: str,
        headers: dict[str, str] | None = None,
        timeout_ms: int = 30000,
        rate_limiter: RateLimiter | None = None,
        max_pages: int | None = None,
        parser: str = "lxml",
    ) -> None:
        """Initialize HTML adapter.

        Args:
            base_url: Base URL for the job listings page.
            headers: Optional HTTP headers (User-Agent, etc.).
            timeout_ms: Request timeout in milliseconds.
            rate_limiter: Optional rate limiter.
            max_pages: Maximum pages to fetch (None = unlimited).
            parser: BeautifulSoup parser to use ("lxml", "html.parser").
        """
        self._base_url = base_url
        self._headers = headers or self._default_headers()
        self._timeout_ms = timeout_ms
        self._rate_limiter = rate_limiter
        self._max_pages = max_pages
        self._parser = parser
        self._client: httpx.AsyncClient | None = None

    def _default_headers(self) -> dict[str, str]:
        """Return default HTTP headers for HTML scraping.

        Returns:
            Dict of default headers including User-Agent.
        """
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

    @property
    def adapter_type(self) -> str:
        """Return the adapter type."""
        return "html"

    @property
    def base_url(self) -> str:
        """Return the base URL."""
        return self._base_url

    @abstractmethod
    def _get_listing_url(self, page: int = 1) -> str:
        """Get the listing page URL.

        Args:
            page: Page number (1-indexed).

        Returns:
            Full URL for the listing page.
        """
        ...

    @abstractmethod
    def _get_job_listing_config(self) -> JobListingConfig:
        """Get the selector configuration for extracting job listings.

        Returns:
            JobListingConfig with container selector and field mappings.
        """
        ...

    @abstractmethod
    def _transform_job(
        self,
        extracted_job: dict[str, Any],
        base_url: str,
    ) -> RawJobData | None:
        """Transform extracted job data to RawJobData.

        Args:
            extracted_job: Dict of extracted fields from the HTML.
            base_url: Base URL for resolving relative URLs.

        Returns:
            RawJobData object or None if the job should be skipped.
        """
        ...

    def _get_pagination_config(self) -> PaginationConfig:
        """Get pagination configuration.

        Override this method if the page uses pagination.

        Returns:
            PaginationConfig with pagination settings.
        """
        return PaginationConfig(
            next_button_selector=None,
            max_pages=self._max_pages,
            base_url=self._base_url,
        )

    def _should_scrape_page(self, page: int, job_count: int) -> bool:
        """Determine if pagination should continue.

        Override this method for custom pagination logic.

        Args:
            page: Current page number.
            job_count: Number of jobs found on this page.

        Returns:
            True if the next page should be scraped.
        """
        config = self._get_pagination_config()
        return should_continue_pagination(
            current_page=page,
            max_pages=config.max_pages,
            job_count=job_count,
        )

    async def fetch_jobs(self) -> ExtractionResult:
        """Fetch all jobs from the HTML page(s) with pagination.

        Returns:
            ExtractionResult with all jobs found.
        """
        all_jobs: list[RawJobData] = []
        warnings: list[str] = []
        pages_fetched = 0
        requests_made = 0
        page = 1

        job_config = self._get_job_listing_config()
        pagination_config = self._get_pagination_config()

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self._timeout_ms / 1000),
            headers=self._headers,
            follow_redirects=True,
        ) as client:
            while True:
                if self._rate_limiter:
                    from urllib.parse import urlparse

                    origin = urlparse(self._base_url).netloc
                    await self._rate_limiter.acquire(origin)

                url = self._get_listing_url(page=page)
                requests_made += 1

                try:
                    response = await client.get(url)
                    response.raise_for_status()

                    content_type = response.headers.get("content-type", "")
                    if "text/html" not in content_type:
                        warnings.append(
                            f"Page {page} returned non-HTML content: {content_type}"
                        )
                        break

                    pages_fetched += 1
                    soup = parse_html(response.text, parser=self._parser)

                    # Extract jobs from current page
                    extracted_jobs, page_warnings = extract_all_jobs(
                        soup, job_config, self._base_url
                    )
                    warnings.extend(page_warnings)

                    # Transform to RawJobData
                    for extracted in extracted_jobs:
                        raw = self._transform_job(extracted, self._base_url)
                        if raw:
                            all_jobs.append(raw)

                    # Check if we should continue
                    if not self._should_scrape_page(page, len(extracted_jobs)):
                        break

                    # Check for next page
                    next_url = find_next_page_url(soup, pagination_config)
                    if next_url:
                        page += 1
                        continue

                    # No next page URL, check if we can construct one
                    if pagination_config.page_param and page < (
                        pagination_config.max_pages or 100
                    ):
                        page += 1
                        continue

                    break

                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        warnings.append(
                            f"Rate limited on page {page}, continuing with partial data"
                        )
                    elif e.response.status_code in (401, 403):
                        return ExtractionResult(
                            jobs=all_jobs,
                            status="failed",
                            error=f"Access denied: {e.response.status_code}",
                            pages_fetched=pages_fetched,
                            requests_made=requests_made,
                        )
                    else:
                        warnings.append(f"HTTP error on page {page}: {e}")
                    break

                except httpx.TimeoutException:
                    warnings.append(f"Timeout on page {page}")
                    break

                except Exception as e:
                    warnings.append(f"Error on page {page}: {str(e)}")
                    break

        if not all_jobs and warnings:
            return ExtractionResult(
                jobs=[],
                status="failed",
                warnings=warnings,
                pages_fetched=pages_fetched,
                requests_made=requests_made,
            )

        return ExtractionResult(
            jobs=all_jobs,
            status="success" if all_jobs else "partial",
            warnings=warnings if warnings else [],
            pages_fetched=pages_fetched,
            requests_made=requests_made,
        )

    async def close(self) -> None:
        """Close the HTTP client if open."""
        if self._client:
            await self._client.aclose()
            self._client = None


# ---------------------------------------------------------------------------
# Helper functions for common HTML patterns
# ---------------------------------------------------------------------------


def create_job_listing_config(
    container_selector: str,
    title_selector: str,
    url_selector: str,
    location_selector: str | None = None,
    date_selector: str | None = None,
    url_attribute: str = "href",
) -> JobListingConfig:
    """Create a standard job listing configuration.

    Convenience function for creating common selector configurations.

    Args:
        container_selector: Selector for job listing container.
        title_selector: Selector for job title (text content).
        url_selector: Selector for job URL (extracts attribute).
        location_selector: Optional selector for location.
        date_selector: Optional selector for date posted.
        url_attribute: Attribute to extract for URL.

    Returns:
        JobListingConfig ready for use.
    """
    return JobListingConfig(
        container_selector=container_selector,
        title_selector=title_selector,
        url_selector=url_selector,
        location_selector=location_selector,
        date_selector=date_selector,
        url_attribute=url_attribute,
    )


def extract_date_from_string(date_str: str | None) -> str | None:
    """Extract and normalize a date from a string.

    Args:
        date_str: Raw date string from HTML.

    Returns:
        ISO 8601 formatted date string or None.
    """
    if not date_str:
        return None

    dt = parse_date_string(date_str)
    if dt:
        return dt.isoformat()

    return date_str
