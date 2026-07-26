"""Unit tests for the new HTML/API adapters introduced in Phase 11."""

from __future__ import annotations

from job_board_scraper.adapters.implementations.absolute_security_adapter import (
    AbsoluteSecurityAdapter,
)
from job_board_scraper.adapters.implementations.caloptima_adapter import (
    CalOptimaAdapter,
)
from job_board_scraper.adapters.implementations.electric_power_engineers_adapter import (
    ElectricPowerEngineersAdapter,
)
from job_board_scraper.adapters.implementations.farm_credit_canada_adapter import (
    FarmCreditCanadaAdapter,
)
from job_board_scraper.adapters.implementations.first_west_adapter import (
    FirstWestAdapter,
)
from job_board_scraper.adapters.implementations.iqmetrix_adapter import (
    IqmetrixAdapter,
)

# ---------------------------------------------------------------------------
# API adapter (Farm Credit Canada)
# ---------------------------------------------------------------------------


class TestFarmCreditCanadaAdapter:
    def test_slug_and_url(self) -> None:
        adapter = FarmCreditCanadaAdapter()
        assert adapter.slug == "farm-credit-canada"
        assert "fccfac.wd3.myworkdayjobs.com" in adapter.base_url

    def test_get_listing_url_uses_offset(self) -> None:
        adapter = FarmCreditCanadaAdapter()
        url1 = adapter._get_listing_url(page=1, per_page=50)
        url2 = adapter._get_listing_url(page=2, per_page=50)
        assert "offset=0" in url1
        assert "offset=50" in url2
        assert "limit=50" in url1

    def test_parse_jobs_extracts_titles(self) -> None:
        adapter = FarmCreditCanadaAdapter()
        response = {
            "data": [
                {
                    "jobPostingId": "JOB-1",
                    "title": "Loan Officer",
                    "locations": ["Regina, SK"],
                    "postedOn": "2026-07-20T08:00:00.000Z",
                    "absoluteUrl": "https://example.com/job1",
                }
            ],
            "total": 1,
            "offset": 0,
            "limit": 100,
        }
        jobs = adapter._parse_jobs(response)
        assert len(jobs) == 1
        assert jobs[0].title == "Loan Officer"
        assert jobs[0].location == "Regina, SK"
        assert jobs[0].source_job_id == "JOB-1"

    def test_parse_jobs_skips_without_url(self) -> None:
        adapter = FarmCreditCanadaAdapter()
        jobs = adapter._parse_jobs({"data": [{"title": "X", "locations": []}]})
        assert jobs == []

    def test_get_pagination_detects_next(self) -> None:
        adapter = FarmCreditCanadaAdapter()
        page = adapter._get_pagination(
            {"data": [{"title": "A"}], "total": 200, "offset": 100, "limit": 100}
        )
        assert page is not None
        assert page["has_next"] is True
        assert page["total"] == 200

    def test_get_pagination_stops_at_end(self) -> None:
        adapter = FarmCreditCanadaAdapter()
        page = adapter._get_pagination(
            {"data": [{"title": "x"}] * 100, "total": 100, "offset": 0, "limit": 100}
        )
        assert page["has_next"] is False


# ---------------------------------------------------------------------------
# HTML adapter helpers
# ---------------------------------------------------------------------------


def _html_with_jobs(container: str, items: list[dict]) -> str:
    rows = []
    for item in items:
        rows.append(
            f'<{container}><a href="{item["href"]}">{item["title"]}</a>'
            f'<span class="location">{item.get("location", "Remote")}</span></{container}>'
        )
    return "<html><body>" + "".join(rows) + "</body></html>"


class TestCalOptimaAdapter:
    def test_slug_and_url(self) -> None:
        adapter = CalOptimaAdapter()
        assert adapter.slug == "caloptima"
        assert "pageuppeople.com" in adapter.base_url

    def test_transform_job_extracts_title_and_id(self) -> None:
        adapter = CalOptimaAdapter()
        raw = {"title": "Data Analyst", "url": "https://example.com/job/abc-123"}
        out = adapter._transform_job(raw, adapter.base_url)
        assert out is not None
        assert out.title == "Data Analyst"
        assert out.source_job_id == "abc-123"


class TestIqmetrixAdapter:
    def test_slug(self) -> None:
        adapter = IqmetrixAdapter()
        assert adapter.slug == "iqmetrix"

    def test_transform_job_extracts_id(self) -> None:
        adapter = IqmetrixAdapter()
        raw = {
            "title": "QA Engineer",
            "url": "https://iqmetrix.applytojob.com/apply/qA1",
        }
        out = adapter._transform_job(raw, adapter.base_url)
        assert out is not None
        assert out.source_job_id == "qA1"


class TestFirstWestAdapter:
    def test_slug(self) -> None:
        adapter = FirstWestAdapter()
        assert adapter.slug == "first-west"

    def test_transform_job_returns_raw(self) -> None:
        adapter = FirstWestAdapter()
        raw = {
            "title": "Member Service Rep",
            "url": "https://careers.firstwestcu.ca/jobs/1",
        }
        out = adapter._transform_job(raw, adapter.base_url)
        assert out is not None
        assert out.title == "Member Service Rep"


class TestElectricPowerEngineersAdapter:
    def test_slug(self) -> None:
        adapter = ElectricPowerEngineersAdapter()
        assert adapter.slug == "electric-power-engineers"

    def test_listing_url(self) -> None:
        adapter = ElectricPowerEngineersAdapter()
        url1 = adapter._get_listing_url(page=1)
        url3 = adapter._get_listing_url(page=3)
        assert "EPE-Engineering-Jobs" in url1
        assert "page=3" in url3


class TestAbsoluteSecurityAdapter:
    def test_slug(self) -> None:
        adapter = AbsoluteSecurityAdapter()
        assert adapter.slug == "absolute-security"

    def test_transform_job_extracts_id(self) -> None:
        adapter = AbsoluteSecurityAdapter()
        raw = {
            "title": "Mobile Engineer",
            "url": "https://jobs.jobvite.com/absolute/job/abc1234",
        }
        out = adapter._transform_job(raw, adapter.base_url)
        assert out is not None
        assert out.source_job_id == "abc1234"
