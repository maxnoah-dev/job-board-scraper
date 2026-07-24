"""Tests for HTML adapters."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from job_board_scraper.adapters.implementations.startup_xyz_adapter import (
    StartupXYZAdapter,
)
from job_board_scraper.adapters.implementations.techcorp_adapter import TechCorpAdapter
from job_board_scraper.adapters.protocols.html_adapter import (
    create_job_listing_config,
    extract_date_from_string,
)

# ---------------------------------------------------------------------------
# TechCorpAdapter tests
# ---------------------------------------------------------------------------


class TestTechCorpAdapter:
    """Tests for TechCorpAdapter."""

    @pytest.fixture
    def adapter(self) -> TechCorpAdapter:
        """Create a TechCorpAdapter instance."""
        return TechCorpAdapter()

    def test_adapter_properties(self, adapter: TechCorpAdapter) -> None:
        """Should have correct adapter properties."""
        assert adapter.slug == "techcorp"
        assert adapter.adapter_type == "html"
        assert "techcorp.example" in adapter.base_url

    def test_get_listing_url_page_1(self, adapter: TechCorpAdapter) -> None:
        """Should return base URL for page 1."""
        url = adapter._get_listing_url(page=1)
        assert "careers" in url
        assert "page=" not in url

    def test_get_listing_url_page_2(self, adapter: TechCorpAdapter) -> None:
        """Should include page param for subsequent pages."""
        url = adapter._get_listing_url(page=2)
        assert "page=2" in url

    def test_get_job_listing_config(self, adapter: TechCorpAdapter) -> None:
        """Should return valid job listing config."""
        config = adapter._get_job_listing_config()
        assert config.container_selector == ".job-card"
        assert ".job-title" in config.title_selector

    def test_get_pagination_config(self, adapter: TechCorpAdapter) -> None:
        """Should return pagination config."""
        config = adapter._get_pagination_config()
        assert config.next_button is not None
        assert config.page_param == "page"

    def test_transform_job_valid(self, adapter: TechCorpAdapter) -> None:
        """Should transform valid job data."""
        extracted = {
            "title": "Software Engineer",
            "url": "https://techcorp.example/careers/123",
            "location": "New York, NY",
        }
        raw = adapter._transform_job(extracted, "https://techcorp.example")

        assert raw is not None
        assert raw.title == "Software Engineer"
        assert raw.source_company_id == "techcorp"
        assert raw.location == "New York, NY"

    def test_transform_job_missing_title(self, adapter: TechCorpAdapter) -> None:
        """Should return None for missing title."""
        extracted = {"url": "https://example.com/job/1"}
        raw = adapter._transform_job(extracted, "https://example.com")
        assert raw is None

    def test_transform_job_missing_url(self, adapter: TechCorpAdapter) -> None:
        """Should return None for missing URL."""
        extracted = {"title": "Software Engineer"}
        raw = adapter._transform_job(extracted, "https://example.com")
        assert raw is None

    def test_extract_job_id_from_url(self, adapter: TechCorpAdapter) -> None:
        """Should extract job ID from URL."""
        assert adapter._extract_job_id("/careers/123") == "123"
        assert adapter._extract_job_id("/careers/456") == "456"

    def test_extract_job_id_no_match(self, adapter: TechCorpAdapter) -> None:
        """Should return None when no job ID found."""
        assert adapter._extract_job_id("/about") is None
        assert adapter._extract_job_id("") is None


# ---------------------------------------------------------------------------
# StartupXYZAdapter tests
# ---------------------------------------------------------------------------


class TestStartupXYZAdapter:
    """Tests for StartupXYZAdapter."""

    @pytest.fixture
    def adapter(self) -> StartupXYZAdapter:
        """Create a StartupXYZAdapter instance."""
        return StartupXYZAdapter()

    def test_adapter_properties(self, adapter: StartupXYZAdapter) -> None:
        """Should have correct adapter properties."""
        assert adapter.slug == "startupxyz"
        assert adapter.adapter_type == "html"
        assert "startupxyz.example" in adapter.base_url

    def test_get_listing_url(self, adapter: StartupXYZAdapter) -> None:
        """Should return correct listing URL."""
        url = adapter._get_listing_url()
        assert "/jobs" in url

    def test_get_job_listing_config(self, adapter: StartupXYZAdapter) -> None:
        """Should return valid job listing config."""
        config = adapter._get_job_listing_config()
        assert config.container_selector == ".job-row"

    def test_transform_job_valid(self, adapter: StartupXYZAdapter) -> None:
        """Should transform valid job data."""
        extracted = {
            "title": "Senior Developer",
            "url": "https://startupxyz.example.com/jobs/456",
            "location": "San Francisco",
        }
        raw = adapter._transform_job(extracted, "https://startupxyz.example.com")

        assert raw is not None
        assert raw.title == "Senior Developer"
        assert raw.source_company_id == "startupxyz"

    def test_transform_job_remote_default(self, adapter: StartupXYZAdapter) -> None:
        """Should default location to Remote."""
        extracted = {
            "title": "Developer",
            "url": "https://example.com/job",
        }
        raw = adapter._transform_job(extracted, "https://example.com")

        assert raw is not None
        assert raw.location == "Remote"


# ---------------------------------------------------------------------------
# Helper functions tests
# ---------------------------------------------------------------------------


class TestCreateJobListingConfig:
    """Tests for create_job_listing_config helper."""

    def test_create_config_required_fields(self) -> None:
        """Should create config with required fields only."""
        config = create_job_listing_config(
            container_selector=".job",
            title_selector=".title",
            url_selector="a",
        )

        assert config.container_selector == ".job"
        assert config.title_selector == ".title"
        assert config.url_selector == "a"

    def test_create_config_with_location(self) -> None:
        """Should include location when specified."""
        config = create_job_listing_config(
            container_selector=".job",
            title_selector=".title",
            url_selector="a",
            location_selector=".location",
        )

        assert config.location_selector == ".location"

    def test_create_config_with_date(self) -> None:
        """Should include date when specified."""
        config = create_job_listing_config(
            container_selector=".job",
            title_selector=".title",
            url_selector="a",
            date_selector=".date",
        )

        assert config.date_selector == ".date"


class TestExtractDateFromString:
    """Tests for extract_date_from_string helper."""

    def test_extract_iso_date(self) -> None:
        """Should parse ISO date."""
        result = extract_date_from_string("2026-07-15")
        assert result is not None
        assert "2026-07-15" in result

    def test_extract_none(self) -> None:
        """Should return None for None input."""
        result = extract_date_from_string(None)
        assert result is None

    def test_extract_invalid(self) -> None:
        """Should return original string for invalid dates."""
        result = extract_date_from_string("not a date")
        assert result == "not a date"


# ---------------------------------------------------------------------------
# Integration tests (mocked HTTP)
# ---------------------------------------------------------------------------


class TestHtmlAdapterFetchJobs:
    """Integration tests for HTML adapter with mocked HTTP."""

    @pytest.fixture
    def adapter(self) -> TechCorpAdapter:
        """Create adapter with mocked client."""
        return TechCorpAdapter(timeout_ms=5000)

    @pytest.fixture
    def sample_html(self) -> str:
        """Sample job listing HTML."""
        return """
        <html>
        <body>
            <div class="job-card">
                <h3 class="job-title">Software Engineer</h3>
                <div class="job-meta">
                    <span class="location">New York, NY</span>
                </div>
                <a href="/careers/123" class="job-link">View Details</a>
            </div>
            <div class="job-card">
                <h3 class="job-title">Product Manager</h3>
                <div class="job-meta">
                    <span class="location">Remote</span>
                </div>
                <a href="/careers/456" class="job-link">View Details</a>
            </div>
        </body>
        </html>
        """

    @pytest.mark.asyncio
    async def test_fetch_jobs_success(
        self, adapter: TechCorpAdapter, sample_html: str
    ) -> None:
        """Should fetch and parse jobs from HTML."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = sample_html

        with (
            patch.object(
                adapter,
                "_get_listing_url",
                return_value="https://techcorp.example/careers",
            ),
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await adapter.fetch_jobs()

            assert len(result.jobs) == 2
            assert result.pages_fetched >= 1

    @pytest.mark.asyncio
    async def test_fetch_jobs_http_error(self, adapter: TechCorpAdapter) -> None:
        """Should handle HTTP errors gracefully."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_error = Exception("Not Found")
        mock_error.response = mock_response

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = mock_error
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await adapter.fetch_jobs()

            assert len(result.warnings) > 0 or result.error is not None

    @pytest.mark.asyncio
    async def test_fetch_jobs_timeout(self, adapter: TechCorpAdapter) -> None:
        """Should handle timeout errors."""
        import httpx

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.TimeoutException("Timeout")
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await adapter.fetch_jobs()

            assert len(result.warnings) > 0
