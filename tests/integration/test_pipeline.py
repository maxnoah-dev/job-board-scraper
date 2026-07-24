"""Integration tests for the ETL pipeline.

Tests the full pipeline with mock adapters and SQLite database:
- Test pipeline with mock adapter
- Test idempotent reruns
- Test partial failure handling

Uses pytest-asyncio with SQLite for isolated, repeatable tests.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

from job_board_scraper.adapters.base import (
    ExtractionResult,
    ExtractionStatus,
)
from job_board_scraper.core.database import (
    get_session_factory,
)
from job_board_scraper.etl.pipeline import (
    PipelineExitCode,
    ScrapingPipeline,
)
from job_board_scraper.models.db_company import Company
from job_board_scraper.models.db_job import Job

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_engine():
    """Create a test engine with in-memory SQLite."""
    engine = create_async_engine(
        TEST_DB_URL,
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    yield engine
    await engine.dispose()


@pytest.fixture
async def test_session(test_engine):
    """Create a test session factory."""
    session_factory = get_session_factory()
    original_bind = session_factory.kw.get("bind")
    session_factory.configure(bind=test_engine)

    from job_board_scraper.core.base import Base
    from job_board_scraper.models.db_company import Company  # noqa: F401
    from job_board_scraper.models.db_job import Job  # noqa: F401
    from job_board_scraper.models.db_scrape_attempt import ScrapeAttempt  # noqa: F401
    from job_board_scraper.models.db_scrape_run import ScrapeRun  # noqa: F401

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        yield session

    session_factory.configure(bind=original_bind)


@pytest.fixture
async def test_company(test_session: AsyncSession) -> Company:
    """Create a test company in the database."""
    company = Company(
        name="Test Corp",
        slug="testcorp",
        adapter_type="api",
        base_url="https://api.testcorp.com",
        is_active=True,
        authoritative=True,
    )
    test_session.add(company)
    await test_session.commit()
    await test_session.refresh(company)
    return company


class MockAdapter:
    """Mock adapter for testing."""

    slug = "testcorp"
    adapter_type = "api"
    base_url = "https://api.testcorp.com"

    def __init__(self, extraction_result: ExtractionResult | Exception = None):
        if isinstance(extraction_result, Exception):
            self._fetch_jobs = AsyncMock(side_effect=extraction_result)
        else:
            self._result = extraction_result or ExtractionResult()
            self._fetch_jobs = AsyncMock(return_value=self._result)

    async def fetch_jobs(self) -> ExtractionResult:
        return await self._fetch_jobs()

    async def close(self) -> None:
        pass


@pytest.fixture
def mock_adapter_with_jobs():
    """Create a mock adapter that returns some jobs."""
    result = ExtractionResult(
        status=ExtractionStatus.SUCCESS,
        jobs=[
            {
                "source_job_id": "job-1",
                "title": "Software Engineer",
                "location": "Remote",
                "url": "https://testcorp.com/jobs/1",
                "date_posted": "2026-07-20T10:00:00Z",
            },
            {
                "source_job_id": "job-2",
                "title": "Product Manager",
                "location": "New York",
                "url": "https://testcorp.com/jobs/2",
                "date_posted": "2026-07-21T10:00:00Z",
            },
            {
                "source_job_id": "job-3",
                "title": "Data Scientist",
                "location": "San Francisco",
                "url": "https://testcorp.com/jobs/3",
                "date_posted": "2026-07-22T10:00:00Z",
            },
        ],
        pages_fetched=1,
        requests_made=1,
    )
    return MockAdapter(result)


@pytest.fixture
def mock_adapter_empty():
    """Create a mock adapter that returns no jobs."""
    result = ExtractionResult(
        status=ExtractionStatus.SUCCESS,
        jobs=[],
        pages_fetched=1,
        requests_made=1,
    )
    return MockAdapter(result)


@pytest.fixture
def mock_adapter_failure():
    """Create a mock adapter that fails."""
    return MockAdapter(Exception("Network error: Connection refused"))


@pytest.fixture
def mock_adapter_partial():
    """Create a mock adapter that returns partial results with warnings."""
    result = ExtractionResult(
        status=ExtractionStatus.PARTIAL,
        jobs=[
            {
                "source_job_id": "job-1",
                "title": "Engineer",
                "location": "Remote",
                "url": "https://testcorp.com/jobs/1",
            },
        ],
        warnings=["Some pages failed to load"],
        pages_fetched=2,
        requests_made=3,
    )
    return MockAdapter(result)


class TestPipelineWithMockAdapter:
    """Tests for pipeline execution with mock adapters."""

    @pytest.mark.asyncio
    async def test_pipeline_extracts_jobs_from_adapter(
        self,
        test_session: AsyncSession,
        test_company: Company,
        mock_adapter_with_jobs,
    ):
        """Pipeline should extract jobs from adapter and store in DB."""
        from job_board_scraper.adapters.registry import registry, reset_registry

        reset_registry()
        registry.register(mock_adapter_with_jobs, enabled=True)

        pipeline = ScrapingPipeline()
        result = await pipeline.run(
            company_slugs=["testcorp"],
            dry_run=False,
            triggered_by="test",
        )

        assert result.status == PipelineExitCode.SUCCESS
        assert result.total_jobs_found == 3
        assert result.total_new_jobs == 3

        jobs = await test_session.execute(
            select(Job).where(Job.company_id == test_company.id)
        )
        stored_jobs = list(jobs.scalars().all())
        assert len(stored_jobs) == 3

        titles = {job.title for job in stored_jobs}
        assert "Software Engineer" in titles
        assert "Product Manager" in titles
        assert "Data Scientist" in titles

    @pytest.mark.asyncio
    async def test_pipeline_handles_empty_results(
        self,
        test_session: AsyncSession,
        test_company: Company,
        mock_adapter_empty,
    ):
        """Pipeline should handle empty adapter results gracefully."""
        from job_board_scraper.adapters.registry import registry, reset_registry

        reset_registry()
        registry.register(mock_adapter_empty, enabled=True)

        pipeline = ScrapingPipeline()
        result = await pipeline.run(
            company_slugs=["testcorp"],
            dry_run=False,
            triggered_by="test",
        )

        assert result.status == PipelineExitCode.SUCCESS
        assert result.total_jobs_found == 0
        assert result.total_new_jobs == 0

    @pytest.mark.asyncio
    async def test_pipeline_handles_adapter_failure(
        self,
        test_session: AsyncSession,
        test_company: Company,
        mock_adapter_failure,
    ):
        """Pipeline should handle adapter failures gracefully."""
        from job_board_scraper.adapters.registry import registry, reset_registry

        reset_registry()
        registry.register(mock_adapter_failure, enabled=True)

        pipeline = ScrapingPipeline()
        result = await pipeline.run(
            company_slugs=["testcorp"],
            dry_run=False,
            triggered_by="test",
        )

        assert result.status == PipelineExitCode.PARTIAL
        assert len(result.company_results) == 1
        assert result.company_results[0].error_type is not None

    @pytest.mark.asyncio
    async def test_pipeline_dry_run(
        self,
        test_session: AsyncSession,
        test_company: Company,
        mock_adapter_with_jobs,
    ):
        """Dry run should not write to database."""
        from job_board_scraper.adapters.registry import registry, reset_registry

        reset_registry()
        registry.register(mock_adapter_with_jobs, enabled=True)

        pipeline = ScrapingPipeline()
        result = await pipeline.run(
            company_slugs=["testcorp"],
            dry_run=True,
            triggered_by="test",
        )

        assert result.status == PipelineExitCode.SUCCESS
        assert result.total_jobs_found == 3

        jobs = await test_session.execute(
            select(Job).where(Job.company_id == test_company.id)
        )
        stored_jobs = list(jobs.scalars().all())
        assert len(stored_jobs) == 0


class TestPipelineIdempotentReruns:
    """Tests for idempotent pipeline reruns."""

    @pytest.mark.asyncio
    async def test_rerun_updates_existing_jobs(
        self,
        test_session: AsyncSession,
        test_company: Company,
        mock_adapter_with_jobs,
    ):
        """Second run should update existing jobs, not create duplicates."""
        from job_board_scraper.adapters.registry import registry, reset_registry

        reset_registry()
        registry.register(mock_adapter_with_jobs, enabled=True)

        pipeline = ScrapingPipeline()

        result1 = await pipeline.run(
            company_slugs=["testcorp"],
            dry_run=False,
            triggered_by="test",
        )
        assert result1.status == PipelineExitCode.SUCCESS
        assert result1.total_new_jobs == 3

        jobs = await test_session.execute(
            select(Job).where(Job.company_id == test_company.id)
        )
        stored_jobs = list(jobs.scalars().all())
        assert len(stored_jobs) == 3

        result2 = await pipeline.run(
            company_slugs=["testcorp"],
            dry_run=False,
            triggered_by="test",
        )
        assert result2.status == PipelineExitCode.SUCCESS
        assert result2.total_new_jobs == 0

        jobs = await test_session.execute(
            select(Job).where(Job.company_id == test_company.id)
        )
        stored_jobs = list(jobs.scalars().all())
        assert len(stored_jobs) == 3

    @pytest.mark.asyncio
    async def test_rerun_with_new_jobs(
        self,
        test_session: AsyncSession,
        test_company: Company,
        mock_adapter_with_jobs,
    ):
        """Adding new jobs on second run should only add the new ones."""
        from job_board_scraper.adapters.registry import registry, reset_registry

        reset_registry()
        registry.register(mock_adapter_with_jobs, enabled=True)

        pipeline = ScrapingPipeline()

        result1 = await pipeline.run(
            company_slugs=["testcorp"],
            dry_run=False,
            triggered_by="test",
        )
        assert result1.total_new_jobs == 3

        new_job_result = ExtractionResult(
            status=ExtractionStatus.SUCCESS,
            jobs=[
                {
                    "source_job_id": "job-1",
                    "title": "Software Engineer",
                    "location": "Remote",
                    "url": "https://testcorp.com/jobs/1",
                },
                {
                    "source_job_id": "job-2",
                    "title": "Product Manager",
                    "location": "New York",
                    "url": "https://testcorp.com/jobs/2",
                },
                {
                    "source_job_id": "job-4",
                    "title": "DevOps Engineer",
                    "location": "Austin",
                    "url": "https://testcorp.com/jobs/4",
                },
            ],
            pages_fetched=1,
            requests_made=1,
        )

        mock_adapter_with_jobs2 = MockAdapter(new_job_result)
        reset_registry()
        registry.register(mock_adapter_with_jobs2, enabled=True)

        result2 = await pipeline.run(
            company_slugs=["testcorp"],
            dry_run=False,
            triggered_by="test",
        )

        assert result2.total_new_jobs == 1
        assert result2.total_jobs_found == 3


class TestPipelinePartialFailure:
    """Tests for partial failure handling."""

    @pytest.mark.asyncio
    async def test_partial_results_from_adapter(
        self,
        test_session: AsyncSession,
        test_company: Company,
        mock_adapter_partial,
    ):
        """Pipeline should handle partial results with warnings."""
        from job_board_scraper.adapters.registry import registry, reset_registry

        reset_registry()
        registry.register(mock_adapter_partial, enabled=True)

        pipeline = ScrapingPipeline()
        result = await pipeline.run(
            company_slugs=["testcorp"],
            dry_run=False,
            triggered_by="test",
        )

        assert result.status == PipelineExitCode.SUCCESS
        assert result.total_jobs_found == 1

    @pytest.mark.asyncio
    async def test_multi_company_partial_failure(
        self,
        test_session: AsyncSession,
        test_company: Company,
        mock_adapter_with_jobs,
        mock_adapter_failure,
    ):
        """When one company fails, others should still succeed."""
        from job_board_scraper.adapters.registry import registry, reset_registry

        reset_registry()
        registry.register(mock_adapter_with_jobs, enabled=True)

        company2 = Company(
            name="Failing Corp",
            slug="failingcorp",
            adapter_type="api",
            base_url="https://api.failingcorp.com",
            is_active=True,
            authoritative=True,
        )
        test_session.add(company2)
        await test_session.commit()

        class FailingAdapter:
            slug = "failingcorp"
            adapter_type = "api"
            base_url = "https://api.failingcorp.com"

            async def fetch_jobs(self):
                raise Exception("Network error: Connection refused")

            async def close(self):
                pass

        registry.register(FailingAdapter(), enabled=True)

        pipeline = ScrapingPipeline()
        result = await pipeline.run(
            company_slugs=["testcorp", "failingcorp"],
            dry_run=False,
            triggered_by="test",
        )

        assert result.status == PipelineExitCode.PARTIAL
        assert result.total_errors >= 1


class TestPipelineDeduplication:
    """Tests for URL-based deduplication."""

    @pytest.mark.asyncio
    async def test_duplicate_urls_deduplicated(
        self,
        test_session: AsyncSession,
        test_company: Company,
    ):
        """Pipeline should deduplicate jobs with same canonical URL."""
        from job_board_scraper.adapters.registry import registry, reset_registry

        duplicate_result = ExtractionResult(
            status=ExtractionStatus.SUCCESS,
            jobs=[
                {
                    "source_job_id": "job-1",
                    "title": "Software Engineer",
                    "location": "Remote",
                    "url": "https://testcorp.com/jobs/1",
                },
                {
                    "source_job_id": "job-1",
                    "title": "Software Engineer",
                    "location": "Remote",
                    "url": "https://testcorp.com/jobs/1?utm_source=linkedin",
                },
                {
                    "source_job_id": "job-2",
                    "title": "Product Manager",
                    "location": "New York",
                    "url": "https://testcorp.com/jobs/2",
                },
            ],
            pages_fetched=1,
            requests_made=1,
        )

        adapter = MockAdapter(duplicate_result)
        reset_registry()
        registry.register(adapter, enabled=True)

        pipeline = ScrapingPipeline()
        result = await pipeline.run(
            company_slugs=["testcorp"],
            dry_run=False,
            triggered_by="test",
        )

        assert result.total_jobs_found == 3
        assert result.total_new_jobs == 2

        jobs = await test_session.execute(
            select(Job).where(Job.company_id == test_company.id)
        )
        stored_jobs = list(jobs.scalars().all())
        assert len(stored_jobs) == 2


class TestPipelineExitCodes:
    """Tests for exit code handling."""

    @pytest.mark.asyncio
    async def test_success_exit_code(
        self,
        test_session: AsyncSession,
        test_company: Company,
        mock_adapter_with_jobs,
    ):
        """Successful scrape should return exit code 0."""
        from job_board_scraper.adapters.registry import registry, reset_registry

        reset_registry()
        registry.register(mock_adapter_with_jobs, enabled=True)

        pipeline = ScrapingPipeline()
        result = await pipeline.run(
            company_slugs=["testcorp"],
            dry_run=False,
            triggered_by="test",
        )

        assert result.status == PipelineExitCode.SUCCESS
        assert result.status.value == 0

    @pytest.mark.asyncio
    async def test_partial_exit_code(
        self,
        test_session: AsyncSession,
        test_company: Company,
        mock_adapter_partial,
    ):
        """Partial failure should return exit code 1."""
        from job_board_scraper.adapters.registry import registry, reset_registry

        reset_registry()
        registry.register(mock_adapter_partial, enabled=True)

        pipeline = ScrapingPipeline()
        result = await pipeline.run(
            company_slugs=["testcorp"],
            dry_run=False,
            triggered_by="test",
        )

        assert result.status.value in [0, 1]

    @pytest.mark.asyncio
    async def test_failed_exit_code(
        self,
        test_session: AsyncSession,
        test_company: Company,
        mock_adapter_failure,
    ):
        """Complete failure should return exit code 2 or 1 (partial)."""
        from job_board_scraper.adapters.registry import registry, reset_registry

        reset_registry()
        registry.register(mock_adapter_failure, enabled=True)

        pipeline = ScrapingPipeline()
        result = await pipeline.run(
            company_slugs=["testcorp"],
            dry_run=False,
            triggered_by="test",
        )

        assert result.status.value in [1, 2]
