"""Farm Credit Canada adapter.

API adapter for fccfac.wd3.myworkdayjobs.com (Workday ATS).
Tenant: ``fccfac`` (per docs/sources/manifest.md).
"""

from __future__ import annotations

from typing import Any

from job_board_scraper.adapters.protocols.api_adapter import ApiAdapter
from job_board_scraper.models.job import RawJobData


class FarmCreditCanadaAdapter(ApiAdapter):
    """Farm Credit Canada adapter using Workday ATS API.

    Tenant: ``fccfac`` (per manifest).
    Endpoint: https://fccfac.wd3.myworkdayjobs.com/ccx/api/v1/fccfac/jobPostings
    """

    slug = "farm-credit-canada"
    SLUG = "farm-credit-canada"
    TENANT = "fccfac"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            base_url=(
                f"https://{self.TENANT}.wd3.myworkdayjobs.com"
                f"/ccx/api/v1/{self.TENANT}"
            ),
            **kwargs,
        )

    def _get_listing_url(self, page: int = 1, per_page: int = 100) -> str:
        offset = (page - 1) * per_page
        return f"{self._base_url}/jobPostings?offset={offset}&limit={per_page}"

    def _parse_jobs(self, response_data: dict[str, Any]) -> list[RawJobData]:
        jobs: list[RawJobData] = []
        raw_jobs = response_data.get("data", [])
        for job in raw_jobs:
            locations = job.get("locations", [])
            location = locations[0] if locations else "Canada"
            posted_on = job.get("postedOn")
            job_id = job.get("jobPostingId", "")
            absolute_url = job.get("absoluteUrl", "")
            workday_url = job.get("workdayUrl", "")
            url = absolute_url or workday_url
            if not url:
                continue
            jobs.append(
                RawJobData(
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
                        "posted_on": posted_on,
                    },
                )
            )
        return jobs

    def _get_pagination(self, response_data: dict[str, Any]) -> dict[str, Any] | None:
        total = response_data.get("total", 0)
        offset = response_data.get("offset", 0)
        limit = response_data.get("limit", 100)
        data = response_data.get("data", [])
        has_next = (offset + len(data)) < total
        return {
            "has_next": has_next,
            "total": total,
            "current_count": len(data),
            "offset": offset,
            "limit": limit,
        }

    async def close(self) -> None:
        return None
