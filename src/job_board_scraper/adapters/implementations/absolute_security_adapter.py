"""Absolute Security adapter.

HTML adapter for jobs.jobvite.com/absolute/jobs (Jobvite public board).
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


class AbsoluteSecurityAdapter(HtmlAdapter):
    """Absolute Security (Jobvite) careers adapter."""

    slug = "absolute-security"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(base_url="https://jobs.jobvite.com", **kwargs)

    def _get_listing_url(self, page: int = 1) -> str:
        if page == 1:
            return f"{self.base_url}/absolute/jobs"
        return f"{self.base_url}/absolute/jobs?page={page}"

    def _get_job_listing_config(self):
        return create_job_listing_config(
            container_selector="table tbody tr.job, .job-list tr",
            title_selector="a.job-title, td.title a",
            url_selector="a.job-title, td.title a",
            location_selector="td.location, td:nth-child(2)",
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
            location=extracted_job.get("location") or "Remote",
            source_job_id=self._extract_job_id(url),
            raw_data={"extracted_at": extracted_job.get("extracted_at")},
        )

    @staticmethod
    def _extract_job_id(url: str) -> str | None:
        match = re.search(r"/job/([A-Za-z0-9_-]+)", url)
        return match.group(1) if match else None
