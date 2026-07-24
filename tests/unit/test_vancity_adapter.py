"""Unit tests for the Vancity adapter (vancity_adapter.py).

Covers:
- VancityAdapter initialization
- URL construction with pagination
- Job parsing from Workday API response
- Pagination logic
- Adapter registration
"""

from __future__ import annotations

from job_board_scraper.adapters.implementations.vancity_adapter import VancityAdapter


class TestVancityAdapterInit:
    """VancityAdapter initializes with correct configuration."""

    def test_slug_is_vancity(self) -> None:
        adapter = VancityAdapter()
        assert adapter.slug == "vancity"

    def test_adapter_type_is_api(self) -> None:
        adapter = VancityAdapter()
        assert adapter.adapter_type == "api"

    def test_base_url_contains_workday_domain(self) -> None:
        adapter = VancityAdapter()
        assert "wd1.myworkday.com" in adapter.base_url
        assert "vancity" in adapter.base_url

    def test_close_is_noop(self) -> None:
        adapter = VancityAdapter()
        # close should be callable without error
        import asyncio

        asyncio.run(adapter.close())


class TestVancityAdapterGetListingUrl:
    """URL construction follows Workday offset-based pagination."""

    def test_first_page_url(self) -> None:
        adapter = VancityAdapter()
        url = adapter._get_listing_url(page=1, per_page=100)
        assert "offset=0" in url
        assert "limit=100" in url
        assert "/jobPostings" in url

    def test_second_page_url(self) -> None:
        adapter = VancityAdapter()
        url = adapter._get_listing_url(page=2, per_page=100)
        assert "offset=100" in url
        assert "limit=100" in url

    def test_custom_per_page(self) -> None:
        adapter = VancityAdapter()
        url = adapter._get_listing_url(page=1, per_page=50)
        assert "offset=0" in url
        assert "limit=50" in url


class TestVancityAdapterParseJobs:
    """Job parsing extracts correct fields from Workday API response."""

    def test_parse_single_job(self) -> None:
        adapter = VancityAdapter()
        response = {
            "data": [
                {
                    "jobPostingId": "JOB-12345",
                    "title": "Senior Software Engineer",
                    "locations": ["Vancouver, BC"],
                    "subcategory": {"id": "eng-1", "name": "Engineering"},
                    "postedOn": "2026-07-10T08:00:00.000Z",
                    "absoluteUrl": "https://vancity.wd1.myworkday.com/positions/JOB-12345",
                    "workdayUrl": "https://vancity.wd1.myworkday.com/jobs/12345",
                }
            ],
            "total": 1,
            "offset": 0,
            "limit": 100,
        }

        jobs = adapter._parse_jobs(response)

        assert len(jobs) == 1
        job = jobs[0]
        assert job.source_company_id == "vancity"
        assert job.source_job_id == "JOB-12345"
        assert job.title == "Senior Software Engineer"
        assert job.location == "Vancouver, BC"
        assert job.url == "https://vancity.wd1.myworkday.com/positions/JOB-12345"
        assert job.date_posted == "2026-07-10T08:00:00.000Z"

    def test_parse_multiple_jobs(self) -> None:
        adapter = VancityAdapter()
        response = {
            "data": [
                {
                    "jobPostingId": "JOB-001",
                    "title": "Software Engineer",
                    "locations": ["Vancouver, BC"],
                    "postedOn": "2026-07-10T08:00:00.000Z",
                    "absoluteUrl": "https://example.com/001",
                },
                {
                    "jobPostingId": "JOB-002",
                    "title": "Product Manager",
                    "locations": ["Remote"],
                    "postedOn": "2026-07-11T08:00:00.000Z",
                    "absoluteUrl": "https://example.com/002",
                },
            ],
            "total": 2,
            "offset": 0,
            "limit": 100,
        }

        jobs = adapter._parse_jobs(response)

        assert len(jobs) == 2
        assert jobs[0].source_job_id == "JOB-001"
        assert jobs[0].title == "Software Engineer"
        assert jobs[1].source_job_id == "JOB-002"
        assert jobs[1].title == "Product Manager"

    def test_parse_empty_data(self) -> None:
        adapter = VancityAdapter()
        response = {
            "data": [],
            "total": 0,
            "offset": 0,
            "limit": 100,
        }

        jobs = adapter._parse_jobs(response)

        assert len(jobs) == 0

    def test_parse_missing_location_defaults_to_vancouver(self) -> None:
        adapter = VancityAdapter()
        response = {
            "data": [
                {
                    "jobPostingId": "JOB-001",
                    "title": "Engineer",
                    "locations": [],
                    "postedOn": "2026-07-10T08:00:00.000Z",
                    "absoluteUrl": "https://example.com/001",
                }
            ],
            "total": 1,
            "offset": 0,
            "limit": 100,
        }

        jobs = adapter._parse_jobs(response)

        assert len(jobs) == 1
        assert jobs[0].location == "Vancouver, BC"

    def test_parse_multiple_locations_takes_first(self) -> None:
        adapter = VancityAdapter()
        response = {
            "data": [
                {
                    "jobPostingId": "JOB-001",
                    "title": "Engineer",
                    "locations": ["Vancouver, BC", "Victoria, BC", "Remote"],
                    "postedOn": "2026-07-10T08:00:00.000Z",
                    "absoluteUrl": "https://example.com/001",
                }
            ],
            "total": 1,
            "offset": 0,
            "limit": 100,
        }

        jobs = adapter._parse_jobs(response)

        assert len(jobs) == 1
        assert jobs[0].location == "Vancouver, BC"

    def test_parse_missing_optional_fields(self) -> None:
        adapter = VancityAdapter()
        response = {
            "data": [
                {
                    "jobPostingId": "JOB-001",
                    "title": "Engineer",
                    "postedOn": "2026-07-10T08:00:00.000Z",
                }
            ],
            "total": 1,
            "offset": 0,
            "limit": 100,
        }

        jobs = adapter._parse_jobs(response)

        # Job is skipped because no URL is provided (required field)
        assert len(jobs) == 0

    def test_raw_data_contains_full_context(self) -> None:
        adapter = VancityAdapter()
        response = {
            "data": [
                {
                    "jobPostingId": "JOB-001",
                    "title": "Engineer",
                    "locations": ["Vancouver, BC"],
                    "subcategory": {"id": "eng", "name": "Engineering"},
                    "postedOn": "2026-07-10T08:00:00.000Z",
                    "absoluteUrl": "https://example.com/001",
                }
            ],
            "total": 1,
            "offset": 0,
            "limit": 100,
        }

        jobs = adapter._parse_jobs(response)

        assert jobs[0].raw_data is not None
        assert jobs[0].raw_data["job_posting_id"] == "JOB-001"
        assert jobs[0].raw_data["subcategory"] == {"id": "eng", "name": "Engineering"}
        assert jobs[0].raw_data["primary_location"] == "Vancouver, BC"


class TestVancityAdapterPagination:
    """Pagination logic correctly determines if more pages exist."""

    def test_has_next_when_more_pages(self) -> None:
        adapter = VancityAdapter()
        response = {
            "data": [{"jobPostingId": f"JOB-{i}"} for i in range(100)],
            "total": 250,
            "offset": 0,
            "limit": 100,
        }

        pagination = adapter._get_pagination(response)

        assert pagination is not None
        assert pagination["has_next"] is True
        assert pagination["total"] == 250
        assert pagination["current_count"] == 100
        assert pagination["offset"] == 0
        assert pagination["limit"] == 100

    def test_no_next_on_last_page(self) -> None:
        adapter = VancityAdapter()
        response = {
            "data": [{"jobPostingId": f"JOB-{i}"} for i in range(50)],
            "total": 250,
            "offset": 200,
            "limit": 100,
        }

        pagination = adapter._get_pagination(response)

        assert pagination is not None
        assert pagination["has_next"] is False
        assert pagination["current_count"] == 50
        assert pagination["offset"] == 200

    def test_no_next_when_exactly_full(self) -> None:
        adapter = VancityAdapter()
        response = {
            "data": [{"jobPostingId": f"JOB-{i}"} for i in range(100)],
            "total": 100,
            "offset": 0,
            "limit": 100,
        }

        pagination = adapter._get_pagination(response)

        assert pagination is not None
        assert pagination["has_next"] is False
        assert pagination["total"] == 100

    def test_empty_response_has_no_next(self) -> None:
        adapter = VancityAdapter()
        response = {
            "data": [],
            "total": 0,
            "offset": 0,
            "limit": 100,
        }

        pagination = adapter._get_pagination(response)

        assert pagination is not None
        assert pagination["has_next"] is False
        assert pagination["total"] == 0
        assert pagination["current_count"] == 0


class TestVancityAdapterIntegration:
    """Integration-style tests for the full fetch_jobs flow.

    Note: Full integration tests with real HTTP calls would require
    async fixtures and actual/mock servers. Here we test the component
    methods that would be used in a real integration.
    """

    def test_integration_url_and_parse_flow(self) -> None:
        """Test the complete flow from URL generation to parsing."""
        adapter = VancityAdapter()

        # Generate URL for first page
        url = adapter._get_listing_url(page=1, per_page=100)
        assert "offset=0" in url
        assert "limit=100" in url

        # Simulate what the API response would look like
        mock_response = {
            "data": [
                {
                    "jobPostingId": "JOB-001",
                    "title": "Software Engineer",
                    "locations": ["Vancouver, BC"],
                    "postedOn": "2026-07-10T08:00:00.000Z",
                    "absoluteUrl": "https://example.com/001",
                },
                {
                    "jobPostingId": "JOB-002",
                    "title": "Product Manager",
                    "locations": ["Remote"],
                    "postedOn": "2026-07-11T08:00:00.000Z",
                    "absoluteUrl": "https://example.com/002",
                },
            ],
            "total": 2,
            "offset": 0,
            "limit": 100,
        }

        # Parse the response
        jobs = adapter._parse_jobs(mock_response)
        assert len(jobs) == 2

        # Check pagination
        pagination = adapter._get_pagination(mock_response)
        assert pagination is not None
        assert pagination["has_next"] is False  # Only 2 jobs, no more pages
        assert pagination["total"] == 2

    def test_pagination_loop_simulation(self) -> None:
        """Simulate a multi-page pagination loop."""
        adapter = VancityAdapter()

        # Simulate responses for 2 pages
        page1 = {
            "data": [
                {
                    "jobPostingId": f"JOB-{i}",
                    "title": f"Job {i}",
                    "locations": ["BC"],
                    "postedOn": "2026-07-10T08:00:00.000Z",
                    "absoluteUrl": f"https://example.com/{i}",
                }
                for i in range(2)
            ],
            "total": 4,
            "offset": 0,
            "limit": 2,
        }

        page2 = {
            "data": [
                {
                    "jobPostingId": f"JOB-{i}",
                    "title": f"Job {i}",
                    "locations": ["BC"],
                    "postedOn": "2026-07-10T08:00:00.000Z",
                    "absoluteUrl": f"https://example.com/{i}",
                }
                for i in range(2, 4)
            ],
            "total": 4,
            "offset": 2,
            "limit": 2,
        }

        # Simulate pagination loop
        all_jobs = []

        # Page 1
        jobs_p1 = adapter._parse_jobs(page1)
        all_jobs.extend(jobs_p1)
        pagination1 = adapter._get_pagination(page1)
        assert pagination1["has_next"] is True

        # Page 2
        jobs_p2 = adapter._parse_jobs(page2)
        all_jobs.extend(jobs_p2)
        pagination2 = adapter._get_pagination(page2)
        assert pagination2["has_next"] is False

        assert len(all_jobs) == 4
        assert all_jobs[0].source_job_id == "JOB-0"
        assert all_jobs[3].source_job_id == "JOB-3"


class TestVancityAdapterProtocolCompliance:
    """Verify VancityAdapter satisfies the BaseAdapter protocol."""

    def test_implements_base_adapter_protocol(self) -> None:
        from job_board_scraper.adapters.base import BaseAdapter

        adapter = VancityAdapter()
        assert isinstance(adapter, BaseAdapter)

    def test_has_required_attributes(self) -> None:
        adapter = VancityAdapter()
        assert hasattr(adapter, "slug")
        assert hasattr(adapter, "adapter_type")
        assert hasattr(adapter, "base_url")

    def test_has_required_methods(self) -> None:
        adapter = VancityAdapter()
        assert callable(getattr(adapter, "fetch_jobs", None))
        assert callable(getattr(adapter, "close", None))
