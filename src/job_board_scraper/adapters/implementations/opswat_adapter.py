"""OPSWAT adapter.

API adapter for opswat.com/careers (Greenhouse ATS).
Phase 4 vertical slice; lives behind synthetic fixtures until
opswat source is promoted to ``approved`` in the compliance manifest.
"""

from __future__ import annotations

from typing import Any

from job_board_scraper.adapters.protocols.api_adapter import ApiAdapter
from job_board_scraper.models.job import RawJobData


class OpswatAdapter(ApiAdapter):
    """OPSWAT adapter using Greenhouse ATS API.

    Board token: opswat (per manifest)
    API Endpoint: https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs
    """

    SLUG = "opswat"
    BOARD_TOKEN = "opswat"  # noqa: S105 - Board identifier, not a secret

    def __init__(self, **kwargs) -> None:
        super().__init__(
            base_url=f"https://boards-api.greenhouse.io/v1/boards/{self.BOARD_TOKEN}",
            **kwargs,
        )

    @property
    def slug(self) -> str:
        return self.SLUG

    def _get_listing_url(self, page: int = 1, per_page: int = 100) -> str:
        return f"{self._base_url}/jobs?page={page}&per_page={per_page}"

    def _parse_jobs(self, response_data: dict[str, Any]) -> list[RawJobData]:
        """Parse jobs from Greenhouse API response.

        Response shape:
        {
            "jobs": [
                {
                    "id": 12345,
                    "title": "Senior Backend Engineer",
                    "location": {"name": "Ho Chi Minh City, Vietnam"},
                    "updated_at": "2026-07-15T10:30:00Z",
                    "absolute_url": "https://jobs.opswat.com/positions/12345",
                    ...
                }
            ],
            "meta": {"total": 50}
        }
        """
        jobs = []
        raw_jobs = response_data.get("jobs", [])

        for job in raw_jobs:
            # Parse location
            location_data = job.get("location", {})
            location = (
                location_data.get("name", "Remote") if location_data else "Remote"
            )

            # Parse date
            updated_at = job.get("updated_at")

            # Build raw job data
            raw = RawJobData(
                source_company_id=self.slug,
                source_job_id=str(job.get("id", "")),
                title=job.get("title", ""),
                location=location,
                url=job.get("absolute_url", ""),
                date_posted=updated_at,
                raw_data={
                    "department": job.get("department", {}).get("name")
                    if isinstance(job.get("department"), dict)
                    else None,
                    "employment_type": job.get("employment_type"),
                    "internal_job_id": job.get("internal_job_id"),
                },
            )
            jobs.append(raw)

        return jobs

    def _get_pagination(self, response_data: dict[str, Any]) -> dict[str, Any] | None:
        """Get pagination info from Greenhouse response.

        Greenhouse uses meta.total and we're fetching all pages.
        """
        meta = response_data.get("meta", {})
        jobs = response_data.get("jobs", [])

        # Simple pagination: if we got jobs, there might be more
        has_next = len(jobs) == 100  # per_page
        total = meta.get("total", 0)

        return {
            "has_next": has_next,
            "total": total,
            "current_count": len(jobs),
        }

    async def close(self) -> None:
        """Close the adapter and release resources.

        The OpswatAdapter uses httpx.AsyncClient which is managed per-request,
        so no persistent connections need to be closed.
        """
        pass
