"""Vancity adapter.

API adapter for jobs.vancity.com (Workday ATS).
Phase 5 vertical slice; lives behind synthetic fixtures until
vancity source is promoted to ``approved`` in the compliance manifest.
"""

from __future__ import annotations

from typing import Any

from job_board_scraper.adapters.protocols.api_adapter import ApiAdapter
from job_board_scraper.models.job import RawJobData


class VancityAdapter(ApiAdapter):
    """Vancity adapter using Workday ATS API.

    Tenant: vancity (per manifest)
    API Endpoint: https://vancity.wd1.myworkday.com/ccx/api/v1/{tenant}/jobPostings
    """

    SLUG = "vancity"
    TENANT = "vancity"

    def __init__(self, **kwargs) -> None:
        super().__init__(
            base_url=f"https://{self.TENANT}.wd1.myworkday.com/ccx/api/v1/{self.TENANT}",
            **kwargs,
        )

    @property
    def slug(self) -> str:
        return self.SLUG

    def _get_listing_url(self, page: int = 1, per_page: int = 100) -> str:
        """Get the job postings listing URL with pagination.

        Workday uses offset-based pagination:
        - offset: Starting position (0-indexed)
        - limit: Number of results per page

        Args:
            page: Page number (1-indexed)
            per_page: Items per page

        Returns:
            Full URL for the listing endpoint
        """
        offset = (page - 1) * per_page
        return f"{self._base_url}/jobPostings?offset={offset}&limit={per_page}"

    def _parse_jobs(self, response_data: dict[str, Any]) -> list[RawJobData]:
        """Parse jobs from Workday API response.

        Response shape:
        {
            "data": [
                {
                    "jobPostingId": "JOB-12345",
                    "title": "Senior Software Engineer",
                    "locations": ["Vancouver, BC"],
                    "subcategory": {
                        "id": "category-1",
                        "name": "Engineering"
                    },
                    "postedOn": "2026-07-10T08:00:00.000Z",
                    "absoluteUrl": "https://vancity.wd1.myworkday.com/positions/...",
                    "workdayUrl": "https://vancity.wd1.myworkday.com/..."
                }
            ],
            "total": 50,
            "offset": 0,
            "limit": 100
        }

        Args:
            response_data: Parsed JSON response from Workday API

        Returns:
            List of RawJobData objects
        """
        jobs = []
        raw_jobs = response_data.get("data", [])

        for job in raw_jobs:
            # Parse location (Workday returns array of locations)
            locations = job.get("locations", [])
            location = locations[0] if locations else "Vancouver, BC"

            # Parse posted date
            posted_on = job.get("postedOn")

            # Parse job ID
            job_id = job.get("jobPostingId", "")

            # Parse URL - at least one URL field must exist
            absolute_url = job.get("absoluteUrl", "")
            workday_url = job.get("workdayUrl", "")
            url = absolute_url or workday_url

            # Skip jobs without a valid URL
            if not url:
                continue

            # Build raw job data
            raw = RawJobData(
                source_company_id=self.slug,
                source_job_id=job_id,
                title=job.get("title", ""),
                location=location,
                url=url,
                date_posted=posted_on,
                raw_data={
                    "job_posting_id": job_id,
                    "locations": locations,
                    "subcategory": job.get("subcategory"),
                    "primary_location": location,
                    "posted_on": posted_on,
                },
            )
            jobs.append(raw)

        return jobs

    def _get_pagination(self, response_data: dict[str, Any]) -> dict[str, Any] | None:
        """Get pagination info from Workday response.

        Workday provides:
        - total: Total number of jobs
        - offset: Current offset position
        - limit: Items per page

        Args:
            response_data: Parsed JSON response

        Returns:
            Pagination dict with has_next, total, current_count, offset, limit
        """
        total = response_data.get("total", 0)
        offset = response_data.get("offset", 0)
        limit = response_data.get("limit", 100)
        data = response_data.get("data", [])
        current_count = len(data)

        # has_next is True if there are more results
        has_next = (offset + current_count) < total

        return {
            "has_next": has_next,
            "total": total,
            "current_count": current_count,
            "offset": offset,
            "limit": limit,
        }

    async def close(self) -> None:
        """Close the adapter and release resources.

        The VancityAdapter uses httpx.AsyncClient which is managed per-request,
        so no persistent connections need to be closed.
        """
        pass
