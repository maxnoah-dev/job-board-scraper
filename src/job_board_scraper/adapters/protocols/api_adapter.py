"""API/ATS adapter protocol.

Concrete adapter base for sources that expose a REST API or an ATS
(Applicant Tracking System) endpoint (Greenhouse, Workday, Lever,
SmartRecruiters, Teamtailor, etc.).
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any

import httpx

from job_board_scraper.adapters.base import BaseAdapterImpl, ExtractionResult
from job_board_scraper.models.job import RawJobData

if TYPE_CHECKING:
    from job_board_scraper.utils.rate_limiter import RateLimiter
    from job_board_scraper.utils.retry import RetryPolicy


class ApiAdapter(BaseAdapterImpl):
    """Base class for API/ATS adapters.

    Provides common utilities for REST API extraction:
    - HTTP client with timeout and retries
    - Rate limiting
    - Pagination handling
    - JSON parsing

    Subclasses must implement:
    - _get_listing_url() - URL for job listings endpoint
    - _parse_jobs(response) - Parse jobs from API response
    - _get_pagination(response) - Get next page URL/token
    """

    def __init__(
        self,
        base_url: str,
        headers: dict[str, str] | None = None,
        timeout_ms: int = 30000,
        rate_limiter: RateLimiter | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        """Initialize API adapter.

        Args:
            base_url: Base URL for the API
            headers: Optional HTTP headers (Authorization, etc.)
            timeout_ms: Request timeout in milliseconds
            rate_limiter: Optional rate limiter
            retry_policy: Optional retry policy
        """
        self._base_url = base_url
        self._headers = headers or {}
        self._timeout_ms = timeout_ms
        self._rate_limiter = rate_limiter
        self._retry_policy = retry_policy
        self._client: httpx.AsyncClient | None = None

    @property
    def adapter_type(self) -> str:
        return "api"

    @property
    def base_url(self) -> str:
        return self._base_url

    @abstractmethod
    def _get_listing_url(self, page: int = 1, per_page: int = 100) -> str:
        """Get the listing endpoint URL.

        Args:
            page: Page number (1-indexed)
            per_page: Items per page

        Returns:
            Full URL for the listing endpoint
        """
        ...

    @abstractmethod
    def _parse_jobs(self, response_data: dict[str, Any]) -> list[RawJobData]:
        """Parse jobs from API response data.

        Args:
            response_data: Parsed JSON response

        Returns:
            List of RawJobData objects
        """
        ...

    @abstractmethod
    def _get_pagination(self, response_data: dict[str, Any]) -> dict[str, Any] | None:
        """Extract pagination info from response.

        Args:
            response_data: Parsed JSON response

        Returns:
            Pagination dict with 'next_page', 'total', etc. or None
        """
        ...

    async def fetch_jobs(self) -> ExtractionResult:
        """Fetch jobs from the API with pagination.

        Returns:
            ExtractionResult with all jobs found
        """
        all_jobs: list[RawJobData] = []
        warnings: list[str] = []
        pages_fetched = 0
        requests_made = 0
        page = 1
        per_page = 100

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self._timeout_ms / 1000),
            headers=self._headers,
        ) as client:
            while True:
                if self._rate_limiter:
                    await self._rate_limiter.acquire(self.base_url)

                url = self._get_listing_url(page=page, per_page=per_page)
                requests_made += 1

                try:
                    response = await client.get(url)
                    response.raise_for_status()
                    pages_fetched += 1

                    data = response.json()
                    jobs = self._parse_jobs(data)
                    all_jobs.extend(jobs)

                    # Check pagination
                    pagination = self._get_pagination(data)
                    if pagination is None or not pagination.get("has_next", False):
                        break

                    page += 1

                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        warnings.append(
                            f"Rate limited on page {page}, continuing with partial data"
                        )
                        break
                    elif e.response.status_code in (401, 403):
                        return ExtractionResult(
                            jobs=all_jobs,
                            status="failed",
                            error=f"Authentication failed: {e.response.status_code}",
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
            status="success",
            warnings=warnings if warnings else [],
            pages_fetched=pages_fetched,
            requests_made=requests_made,
        )
