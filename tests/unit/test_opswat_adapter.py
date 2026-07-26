"""Unit tests for ``adapters/implementations/opswat_adapter.py``."""

from __future__ import annotations

from job_board_scraper.adapters.implementations.opswat_adapter import OpswatAdapter


def _resp(jobs: list) -> dict:
    return {"jobs": jobs, "meta": {"total": len(jobs)}}


def _job(id: int = 1, title: str = "Engineer") -> dict:
    return {
        "id": id,
        "title": title,
        "absolute_url": f"https://jobs.opswat.com/positions/{id}",
        "location": {"name": "Remote"},
        "updated_at": "2026-01-01T00:00:00Z",
    }


class TestOpswatAdapter:
    def test_slug(self) -> None:
        a = OpswatAdapter()
        assert a.slug == "opswat"

    def test_parse_jobs_empty(self) -> None:
        a = OpswatAdapter()
        assert a._parse_jobs(_resp([])) == []

    def test_parse_jobs_single(self) -> None:
        a = OpswatAdapter()
        records = a._parse_jobs(_resp([_job(1, "Engineer")]))
        assert len(records) == 1
        assert records[0].title == "Engineer"
        assert records[0].source_company_id == "opswat"

    def test_parse_jobs_falls_back_to_remote(self) -> None:
        a = OpswatAdapter()
        job = _job()
        job["location"] = None
        records = a._parse_jobs(_resp([job]))
        assert records[0].location == "Remote"

    def test_parse_jobs_handles_department_as_dict(self) -> None:
        a = OpswatAdapter()
        job = _job()
        job["department"] = {"name": "Engineering"}
        records = a._parse_jobs(_resp([job]))
        assert records[0].raw_data["department"] == "Engineering"

    def test_parse_jobs_handles_department_as_string(self) -> None:
        a = OpswatAdapter()
        job = _job()
        job["department"] = "Engineering"  # not a dict
        records = a._parse_jobs(_resp([job]))
        assert records[0].raw_data["department"] is None

    def test_get_listing_url(self) -> None:
        a = OpswatAdapter()
        url = a._get_listing_url(page=2, per_page=50)
        assert "page=2" in url
        assert "per_page=50" in url

    def test_get_pagination_stops_when_empty(self) -> None:
        a = OpswatAdapter()
        # Empty payload: no more pages
        pag = a._get_pagination({"jobs": [], "meta": {"total": 5}})
        assert pag is None or pag.get("has_next") is False
