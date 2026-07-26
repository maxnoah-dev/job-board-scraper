"""CalOptima adapter.

HTML adapter for CalOptima's PageUp-based careers page.
Source: https://careers.pageuppeople.com/1150/cw/en-us/listing/
"""

from __future__ import annotations

import re
from typing import Any

from job_board_scraper.adapters.protocols.html_adapter import (
    HtmlAdapter,
    create_job_listing_config,
)
from job_board_scraper.models.job import RawJobData
from job_board_scraper.utils.html_parser import PaginationConfig


class CalOptimaAdapter(HtmlAdapter):
    """CalOptima adapter using HTML scrape over PageUp listing."""

    slug = "caloptima"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(base_url="https://careers.pageuppeople.com/1150/cw/en-us/listing", **kwargs)

    def _get_listing_url(self, page: int = 1) -> str:
        if page == 1:
            return f"{self._base_url}/"
        return f"{self._base_url}/?page={page}"

    def _get_job_listing_config(self):
        return create_job_listing_config(
            container_selector="table tbody tr",
            title_selector="a[href*='/job/']",
            url_selector="a[href*='/job/']",
            location_selector="td:nth-child(2)",
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
        # Resolved absolute URL is already passed by extract_all_jobs.
        location = extracted_job.get("location") or "Orange County, CA"
        return RawJobData(
            source_company_id=self.slug,
            title=title.strip(),
            url=url,
            location=location.strip() if isinstance(location, str) else location,
            source_job_id=self._extract_job_id(url),
            raw_data={"extracted_at": extracted_job.get("extracted_at")},
        )

    @staticmethod
    def _extract_job_id(url: str) -> str | None:
        match = re.search(r"/job/([^/?#]+)", url)
        return match.group(1) if match else None
