"""Unit tests for ``etl/pipeline.py`` covering pure helpers and orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from job_board_scraper.etl.pipeline import (
    PipelineExitCode,
    PipelineResult,
    ScrapeResult,
    ScrapingPipeline,
    create_pipeline,
)
from job_board_scraper.models.db_scrape_run import RunStatus


def _sr(status: PipelineExitCode, **kw: object) -> ScrapeResult:
    return ScrapeResult(
        company_id=1,
        company_slug="opswat",
        status=status,
        jobs_found=0,
        new_jobs=0,
        closed_jobs=0,
        **kw,  # type: ignore[arg-type]
    )


class TestPipelineResultProperties:
    def test_duration_seconds_with_finished_at(self) -> None:
        result = PipelineResult(
            run_id=1,
            status=PipelineExitCode.SUCCESS,
            started_at=datetime(2026, 1, 1, 0, 0, 0),
            finished_at=datetime(2026, 1, 1, 0, 0, 12),
        )
        assert result.duration_seconds == pytest.approx(12.0)

    def test_duration_seconds_without_finished_at(self) -> None:
        result = PipelineResult(
            run_id=1,
            status=PipelineExitCode.SUCCESS,
            started_at=datetime.now(UTC),
        )
        assert result.duration_seconds == 0.0

    def test_successful_companies(self) -> None:
        results = [
            _sr(PipelineExitCode.SUCCESS),
            _sr(PipelineExitCode.FAILED),
            _sr(PipelineExitCode.SUCCESS),
        ]
        pipeline = PipelineResult(
            run_id=1,
            status=PipelineExitCode.PARTIAL,
            started_at=datetime.now(UTC),
            company_results=results,
        )
        assert len(pipeline.successful_companies) == 2

    def test_failed_companies(self) -> None:
        results = [
            _sr(PipelineExitCode.SUCCESS),
            _sr(PipelineExitCode.FAILED),
        ]
        pipeline = PipelineResult(
            run_id=1,
            status=PipelineExitCode.PARTIAL,
            started_at=datetime.now(UTC),
            company_results=results,
        )
        assert len(pipeline.failed_companies) == 1


class TestComputeOverallStatus:
    def setup_method(self) -> None:
        self.pipeline = ScrapingPipeline()

    def test_empty_results_is_success(self) -> None:
        assert self.pipeline._compute_overall_status([]) == PipelineExitCode.SUCCESS

    def test_all_success(self) -> None:
        results = [_sr(PipelineExitCode.SUCCESS) for _ in range(3)]
        assert self.pipeline._compute_overall_status(results) == PipelineExitCode.SUCCESS

    def test_one_failed_is_partial(self) -> None:
        results = [
            _sr(PipelineExitCode.SUCCESS),
            _sr(PipelineExitCode.FAILED),
        ]
        assert self.pipeline._compute_overall_status(results) == PipelineExitCode.PARTIAL

    def test_one_partial_is_partial(self) -> None:
        results = [
            _sr(PipelineExitCode.SUCCESS),
            _sr(PipelineExitCode.PARTIAL),
        ]
        assert self.pipeline._compute_overall_status(results) == PipelineExitCode.PARTIAL

    def test_all_failed(self) -> None:
        results = [
            _sr(PipelineExitCode.FAILED),
            _sr(PipelineExitCode.FAILED),
        ]
        assert self.pipeline._compute_overall_status(results) == PipelineExitCode.FAILED


class TestStatusToRunStatus:
    def setup_method(self) -> None:
        self.pipeline = ScrapingPipeline()

    def test_mappings(self) -> None:
        assert self.pipeline._status_to_run_status(PipelineExitCode.SUCCESS) == RunStatus.SUCCESS
        assert self.pipeline._status_to_run_status(PipelineExitCode.PARTIAL) == RunStatus.PARTIAL
        assert self.pipeline._status_to_run_status(PipelineExitCode.FAILED) == RunStatus.FAILED


class TestBuildVilaoTranslator:
    def test_returns_none_when_disabled(self) -> None:
        assert ScrapingPipeline._build_vilao_translator(False) is None

    def test_returns_none_when_key_missing(self, monkeypatch) -> None:
        # patch get_settings so that vilao_api_key resolves to empty
        fake_settings = MagicMock()
        fake_settings.VILAO_ENABLED = True
        fake_settings.VILAO_API_KEY = ""
        fake_settings.VILAO_MODEL = "gx/gpt-5.4"
        fake_settings.VILAO_BASE_URL = "https://api.vilao.ai/v1"
        fake_settings.VILAO_TIMEOUT_S = 15.0
        fake_settings.VILAO_RATE_LIMIT_PER_MIN = 60
        fake_settings.VILAO_FAIL_THRESHOLD = 3
        monkeypatch.setattr(
            "job_board_scraper.core.config.get_settings", lambda: fake_settings
        )
        assert ScrapingPipeline._build_vilao_translator(True) is None

    def test_builds_translator_when_enabled(self, monkeypatch) -> None:
        fake_settings = MagicMock()
        fake_settings.VILAO_ENABLED = True
        fake_settings.VILAO_API_KEY = "sk-test-key"
        fake_settings.VILAO_MODEL = "gx/gpt-5.4"
        fake_settings.VILAO_BASE_URL = "https://api.vilao.ai/v1"
        fake_settings.VILAO_TIMEOUT_S = 15.0
        fake_settings.VILAO_RATE_LIMIT_PER_MIN = 60
        fake_settings.VILAO_FAIL_THRESHOLD = 3
        monkeypatch.setattr(
            "job_board_scraper.core.config.get_settings", lambda: fake_settings
        )
        translator = ScrapingPipeline._build_vilao_translator(True)
        assert translator is not None


class TestCreatePipeline:
    def test_create_pipeline_returns_instance(self) -> None:
        pipeline = create_pipeline()
        assert isinstance(pipeline, ScrapingPipeline)


@pytest.mark.asyncio
class TestPipelineRun:
    async def test_run_no_companies(self) -> None:
        pipeline = ScrapingPipeline()
        # patch _create_run, _get_all_active_companies
        pipeline._create_run = AsyncMock(return_value=42)  # type: ignore[method-assign]
        pipeline._get_all_active_companies = AsyncMock(return_value=[])  # type: ignore[method-assign]
        pipeline._update_run_status = AsyncMock()  # type: ignore[method-assign]
        result = await pipeline.run()
        assert result.run_id == 42
        assert result.status == PipelineExitCode.SUCCESS
        assert result.total_jobs_found == 0

    async def test_run_passes_enable_vilao_to_extractor(self) -> None:
        pipeline = ScrapingPipeline()
        pipeline._create_run = AsyncMock(return_value=1)  # type: ignore[method-assign]
        pipeline._get_all_active_companies = AsyncMock(return_value=[])  # type: ignore[method-assign]
        pipeline._update_run_status = AsyncMock()  # type: ignore[method-assign]
        extractor = MagicMock()
        extractor.set_vilao_translator = MagicMock()
        pipeline._extractor = extractor
        await pipeline.run(enable_vilao=True)
        extractor.set_vilao_translator.assert_called_once()


@pytest.mark.asyncio
class TestScrapeCompanyDryRun:
    async def test_dry_run_success(self) -> None:
        company = MagicMock()
        company.id = 1
        company.slug = "opswat"
        adapter = MagicMock()
        adapter.fetch_jobs = AsyncMock(
            return_value=MagicMock(jobs=[], warnings=[], error=None)
        )
        pipeline = ScrapingPipeline()
        result = await pipeline._scrape_company_dry_run(
            adapter, company, datetime.now(UTC)
        )
        assert result.status == PipelineExitCode.SUCCESS
        assert result.jobs_found == 0

    async def test_dry_run_partial_on_extraction_error(self) -> None:
        company = MagicMock()
        company.id = 1
        company.slug = "opswat"
        adapter = MagicMock()
        adapter.fetch_jobs = AsyncMock(
            return_value=MagicMock(jobs=[], warnings=[], error="boom")
        )
        pipeline = ScrapingPipeline()
        result = await pipeline._scrape_company_dry_run(
            adapter, company, datetime.now(UTC)
        )
        assert result.status == PipelineExitCode.PARTIAL
        assert result.error_type == "ExtractionError"

    async def test_dry_run_failed_on_exception(self) -> None:
        company = MagicMock()
        company.id = 1
        company.slug = "opswat"
        adapter = MagicMock()
        adapter.fetch_jobs = AsyncMock(side_effect=RuntimeError("explode"))
        pipeline = ScrapingPipeline()
        result = await pipeline._scrape_company_dry_run(
            adapter, company, datetime.now(UTC)
        )
        assert result.status == PipelineExitCode.FAILED
        assert result.error_type == "RuntimeError"


@pytest.mark.asyncio
class TestScrapeCompany:
    async def test_no_adapter(self) -> None:
        company = MagicMock()
        company.id = 1
        company.slug = "unknown-co"
        pipeline = ScrapingPipeline()
        with patch(
            "job_board_scraper.adapters.registry.registry.get_or_none",
            return_value=None,
        ):
            result = await pipeline._scrape_company(
                company, run_id=1, dry_run=False
            )
        assert result.status == PipelineExitCode.FAILED
        assert result.error_type == "NoAdapter"
