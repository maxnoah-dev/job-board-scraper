"""Unit tests for ``web/routes/companies.py`` helpers."""

from __future__ import annotations

from datetime import datetime

from job_board_scraper.web.routes.companies import _job_to_dict


class _Job:
    def __init__(
        self,
        id: int = 1,
        title: str = "Engineer",
        location: str = "Remote",
        url: str = "https://example.com",
        status: str = "open",
    ) -> None:
        self.id = id
        self.title = title
        self.location = location
        self.url = url
        self.status = status
        self.date_posted = datetime(2026, 1, 1)


class TestJobToDict:
    def test_includes_company_attrs(self) -> None:
        job = _Job()
        data = _job_to_dict(job)
        assert data["title"] == "Engineer"
        assert data["status"] == "open"
        assert data["company_name"] == ""
        assert data["company_slug"] == ""

    def test_passes_through_extra_attrs(self) -> None:
        job = _Job()
        job.company_name = "OPSWAT"
        job.company_slug = "opswat"
        data = _job_to_dict(job)
        assert data["company_name"] == "OPSWAT"
