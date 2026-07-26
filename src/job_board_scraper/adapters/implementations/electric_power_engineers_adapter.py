"""Electric Power Engineers adapter.

HTML adapter for join.epeconsulting.com (sourced via Jibe / iCIMS-style SPA).
"""

from __future__ import annotations

from typing import Any

from job_board_scraper.adapters.protocols.html_adapter import (
    HtmlAdapter,
    create_job_listing_config,
)
from job_board_scraper.models.job import RawJobData
from job_board_scraper.utils.html_parser import PaginationConfig


class ElectricPowerEngineersAdapter(HtmlAdapter):
    """Electric Power Engineers careers page adapter."""

    slug = "electric-power-engineers"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(base_url="https://join.epeconsulting.com", **kwargs)

    def _get_listing_url(self, page: int = 1) -> str:
        if page == 1:
            return f"{self.base_url}/EPE-Engineering-Jobs/jobs"
        return f"{self.base_url}/EPE-Engineering-Jobs/jobs?page={page}"

    def _get_job_listing_config(self):
        return create_job_listing_config(
            container_selector=".job-listing, article.job",
            title_selector="a",
            url_selector="a",
            location_selector=".job-location, .location",
            url_attribute="href",
        )

    def _get_pagination_config(self) -> PaginationConfig:
        return PaginationConfig(
            next_button="a.next, a[rel='next']",
            page_param="page",
            max_pages=self._max_pages or 20,
            base_url=self._base_url,
        )

    def _transform_job(
        self,
        extracted_job: dict[str, Any],
        base_url: str,
    ) -> RawJobData | None:
        title = extracted_job.get("title")
        url = extracted_job.get("url")
        if not title or not url:
            return None
        return RawJobData(
            source_company_id=self.slug,
            title=title.strip(),
            url=url,
            location=extracted_job.get("location") or "Austin, TX",
            raw_data={"extracted_at": extracted_job.get("extracted_at")},
        )
