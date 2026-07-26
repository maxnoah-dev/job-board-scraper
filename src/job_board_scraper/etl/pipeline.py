"""ETL pipeline module.

Orchestrates the full scrape pipeline: extract → transform → validate →
dedupe → load → reconcile → summary.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from job_board_scraper.adapters.base import BaseAdapter
from job_board_scraper.core.database import session_scope, transactional_session
from job_board_scraper.etl.deduplicator import Deduplicator
from job_board_scraper.etl.extractor import Extractor
from job_board_scraper.etl.loader import Loader
from job_board_scraper.etl.stale_reconciler import StaleReconciler
from job_board_scraper.models.db_company import Company
from job_board_scraper.models.db_scrape_run import RunStatus, ScrapeRun
from job_board_scraper.models.job import JobRecord, RawJobData
from job_board_scraper.repositories.company_repository import CompanyRepository
from job_board_scraper.repositories.job_repository import JobRepository

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class PipelineExitCode(int, Enum):
    """Exit codes for the pipeline CLI.

    Corresponds to ScrapeRun.RunStatus mapping:
    - SUCCESS (0): All companies scraped successfully
    - PARTIAL (1): Some companies failed or had issues
    - FAILED (2): All companies failed or pipeline crashed
    """

    SUCCESS = 0
    PARTIAL = 1
    FAILED = 2


@dataclass
class ScrapeResult:
    """Result of scraping a single company."""

    company_id: int
    company_slug: str
    status: PipelineExitCode
    jobs_found: int = 0
    new_jobs: int = 0
    closed_jobs: int = 0
    records_rejected: int = 0
    error_type: str | None = None
    error_message: str | None = None
    warnings: list[str] = field(default_factory=list)
    duration_ms: int = 0


@dataclass
class PipelineResult:
    """Result of a full pipeline run."""

    run_id: int
    status: PipelineExitCode
    started_at: datetime
    finished_at: datetime | None = None
    company_results: list[ScrapeResult] = field(default_factory=list)
    total_jobs_found: int = 0
    total_new_jobs: int = 0
    total_closed_jobs: int = 0
    total_errors: int = 0

    @property
    def duration_seconds(self) -> float:
        """Calculate total duration in seconds."""
        if self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return 0.0

    @property
    def successful_companies(self) -> list[ScrapeResult]:
        """Get companies that scraped successfully."""
        return [r for r in self.company_results if r.status == PipelineExitCode.SUCCESS]

    @property
    def failed_companies(self) -> list[ScrapeResult]:
        """Get companies that failed."""
        return [r for r in self.company_results if r.status == PipelineExitCode.FAILED]


class ScrapingPipeline:
    """Main ETL pipeline for scraping job listings.

    Orchestrates the complete flow:
    1. Extract: Fetch raw jobs from adapter
    2. Transform: Convert to normalized JobRecord
    3. Validate: Check for data quality issues
    4. Deduplicate: Remove URL duplicates within this run
    5. Load: Transactional upsert to database
    6. Reconcile: Close stale jobs, reopen previously closed ones
    7. Summary: Record metrics and produce report

    Supports both single-company and multi-company runs with proper
    transaction handling and error recovery per company.
    """

    MAX_CONCURRENT_COMPANIES = 5

    def __init__(self) -> None:
        self._extractor = Extractor()
        self._loader = Loader()
        self._deduplicator = Deduplicator()
        self._reconciler = StaleReconciler()
        self._company_repo = CompanyRepository()
        self._job_repo = JobRepository()

    async def run(
        self,
        company_slugs: list[str] | None = None,
        dry_run: bool = False,
        triggered_by: str = "manual",
        enable_vilao: bool = False,
    ) -> PipelineResult:
        """Execute the full scrape pipeline.

        Args:
            company_slugs: Specific companies to scrape. None = all active companies.
            dry_run: If True, skip database writes.
            triggered_by: What triggered this run (e.g., "manual", "scheduled").
            enable_vilao: When True, attach a Vilao LLM translator to the
                transformer so ``JobRecord.title_vi`` is populated.

        Returns:
            PipelineResult with overall status and per-company metrics.
        """
        started_at = datetime.now(UTC)
        logger.info(
            "Pipeline starting",
            extra={
                "company_slugs": company_slugs,
                "dry_run": dry_run,
                "triggered_by": triggered_by,
                "enable_vilao": enable_vilao,
            },
        )

        run_id = await self._create_run(triggered_by)
        company_results: list[ScrapeResult] = []

        try:
            vilao_translator = self._build_vilao_translator(enable_vilao)
            self._extractor.set_vilao_translator(vilao_translator)

            if company_slugs:
                companies = await self._get_companies_by_slugs(company_slugs)
            else:
                companies = await self._get_all_active_companies()

            if not companies:
                logger.warning("No companies to scrape")
                return PipelineResult(
                    run_id=run_id,
                    status=PipelineExitCode.SUCCESS,
                    started_at=started_at,
                    finished_at=datetime.now(UTC),
                    company_results=[],
                )

            semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_COMPANIES)

            async def scrape_with_semaphore(company: Company) -> ScrapeResult:
                async with semaphore:
                    return await self._scrape_company(company, run_id, dry_run)

            results = await asyncio.gather(
                *[scrape_with_semaphore(c) for c in companies],
                return_exceptions=True,
            )

            for result in results:
                if isinstance(result, Exception):
                    logger.exception(
                        "Unexpected error during scraping", exc_info=result
                    )
                    company_results.append(
                        ScrapeResult(
                            company_id=0,
                            company_slug="unknown",
                            status=PipelineExitCode.FAILED,
                            error_type="UnexpectedError",
                            error_message=str(result),
                        )
                    )
                else:
                    company_results.append(result)

            overall_status = self._compute_overall_status(company_results)

        except Exception:
            logger.exception("Pipeline failed unexpectedly")
            await self._update_run_status(run_id, RunStatus.FAILED)
            raise

        finished_at = datetime.now(UTC)
        total_jobs = sum(r.jobs_found for r in company_results)
        total_new = sum(r.new_jobs for r in company_results)
        total_closed = sum(r.closed_jobs for r in company_results)
        total_errors = sum(1 for r in company_results if r.error_type is not None)

        await self._update_run_status(
            run_id, self._status_to_run_status(overall_status)
        )

        pipeline_result = PipelineResult(
            run_id=run_id,
            status=overall_status,
            started_at=started_at,
            finished_at=finished_at,
            company_results=company_results,
            total_jobs_found=total_jobs,
            total_new_jobs=total_new,
            total_closed_jobs=total_closed,
            total_errors=total_errors,
        )

        logger.info(
            "Pipeline finished",
            extra={
                "run_id": run_id,
                "status": overall_status.name,
                "total_jobs": total_jobs,
                "duration_seconds": pipeline_result.duration_seconds,
            },
        )

        return pipeline_result

    async def _scrape_company(
        self,
        company: Company,
        run_id: int,
        dry_run: bool,
    ) -> ScrapeResult:
        """Scrape a single company.

        Args:
            company: Company to scrape
            run_id: Parent scrape run ID
            dry_run: Skip database writes

        Returns:
            ScrapeResult with metrics
        """
        from job_board_scraper.adapters.registry import registry

        start_time = datetime.now(UTC)
        result = ScrapeResult(
            company_id=company.id,
            company_slug=company.slug,
            status=PipelineExitCode.FAILED,
        )

        adapter = registry.get_or_none(company.slug)
        if adapter is None:
            logger.warning(
                "No adapter registered for company", extra={"company": company.slug}
            )
            result.error_type = "NoAdapter"
            result.error_message = f"No adapter registered for {company.slug}"
            return result

        if dry_run:
            return await self._scrape_company_dry_run(adapter, company, start_time)

        async with transactional_session() as session:
            attempt = await self._loader.record_attempt_start(
                session, run_id, company.id
            )

            records: list[JobRecord] = []
            transform_errors: list[tuple[RawJobData, Exception]] = []

            try:
                records, transform_errors = await self._extractor.extract_from_adapter(
                    adapter, company.id
                )

                result.records_rejected = len(transform_errors)
                if transform_errors:
                    result.warnings.append(
                        f"{len(transform_errors)} records failed transformation"
                    )

                unique_records, duplicates = self._deduplicator.deduplicate(records)
                if duplicates:
                    result.warnings.append(f"{len(duplicates)} duplicates removed")

                seen_urls = self._deduplicator.get_seen_urls(unique_records)

                created, updated = await self._loader.load_jobs(
                    session, unique_records, company.id
                )

                closed = await self._loader.close_stale_jobs(
                    session, company.id, seen_urls
                )
                reopened = await self._loader.reopen_closed_jobs(
                    session, company.id, seen_urls
                )

                warnings_str = "; ".join(result.warnings) if result.warnings else None
                await self._loader.record_attempt_success(
                    session,
                    attempt,
                    jobs_found=len(records),
                    new_jobs=len(created),
                    closed_jobs=closed + reopened,
                    records_rejected=result.records_rejected,
                    warnings=warnings_str,
                )

                await session.commit()

                result.jobs_found = len(records)
                result.new_jobs = len(created)
                result.closed_jobs = closed + reopened
                result.status = PipelineExitCode.SUCCESS

            except Exception as e:
                logger.exception(
                    "Scrape failed for company",
                    extra={"company": company.slug, "error": str(e)},
                )
                result.error_type = type(e).__name__
                result.error_message = str(e)
                await self._loader.record_attempt_failure(
                    session,
                    attempt,
                    error_type=result.error_type,
                    error_message=result.error_message,
                    partial=len(records) > 0,
                )
                await session.commit()
                result.status = PipelineExitCode.PARTIAL

        end_time = datetime.now(UTC)
        result.duration_ms = int((end_time - start_time).total_seconds() * 1000)

        return result

    async def _scrape_company_dry_run(
        self,
        adapter: BaseAdapter,
        company: Company,
        start_time: datetime,
    ) -> ScrapeResult:
        """Scrape without database writes.

        Args:
            adapter: Adapter to scrape
            company: Company being scraped
            start_time: Start timestamp

        Returns:
            ScrapeResult with dry-run metrics
        """
        logger.info("Dry run for company", extra={"company": company.slug})
        result = ScrapeResult(
            company_id=company.id,
            company_slug=company.slug,
            status=PipelineExitCode.SUCCESS,
        )

        try:
            extraction_result = await adapter.fetch_jobs()
            result.jobs_found = len(extraction_result.jobs)
            if extraction_result.warnings:
                result.warnings.extend(extraction_result.warnings)
            if extraction_result.error:
                result.error_type = "ExtractionError"
                result.error_message = extraction_result.error
                result.status = PipelineExitCode.PARTIAL
        except Exception as e:
            result.error_type = type(e).__name__
            result.error_message = str(e)
            result.status = PipelineExitCode.FAILED

        end_time = datetime.now(UTC)
        result.duration_ms = int((end_time - start_time).total_seconds() * 1000)

        return result

    async def _create_run(self, triggered_by: str) -> int:
        """Create a new scrape run record.

        Args:
            triggered_by: What triggered this run

        Returns:
            The created run ID
        """
        async with transactional_session() as session:
            run = ScrapeRun(
                started_at=datetime.now(UTC),
                status=RunStatus.RUNNING.value,
                triggered_by=triggered_by,
            )
            session.add(run)
            await session.commit()
            await session.refresh(run)
            return run.id

    async def _update_run_status(
        self,
        run_id: int,
        status: RunStatus,
    ) -> None:
        """Update the status of a scrape run.

        Args:
            run_id: Run ID to update
            status: New status
        """
        from sqlalchemy import update

        async with transactional_session() as session:
            stmt = (
                update(ScrapeRun)
                .where(ScrapeRun.id == run_id)
                .values(
                    status=status.value,
                    finished_at=datetime.now(UTC),
                )
            )
            await session.execute(stmt)
            await session.commit()

    async def _get_companies_by_slugs(
        self,
        slugs: list[str],
    ) -> list[Company]:
        """Get companies by their slugs.

        Args:
            slugs: List of company slugs

        Returns:
            List of Company objects
        """
        companies: list[Company] = []
        async with session_scope() as session:
            for slug in slugs:
                company = await self._company_repo.find_by_slug(session, slug)
                if company:
                    companies.append(company)
                else:
                    logger.warning("Company not found", extra={"slug": slug})
        return companies

    async def _get_all_active_companies(self) -> list[Company]:
        """Get all active companies.

        Returns:
            List of active Company objects
        """
        async with session_scope() as session:
            return await self._company_repo.find_active(session)

    def _compute_overall_status(
        self,
        results: list[ScrapeResult],
    ) -> PipelineExitCode:
        """Compute overall pipeline status from individual results.

        Args:
            results: Per-company scrape results

        Returns:
            Overall status
        """
        if not results:
            return PipelineExitCode.SUCCESS

        failures = sum(1 for r in results if r.status == PipelineExitCode.FAILED)
        partials = sum(1 for r in results if r.status == PipelineExitCode.PARTIAL)

        total = len(results)

        if failures == total:
            return PipelineExitCode.FAILED
        if failures > 0 or partials > 0:
            return PipelineExitCode.PARTIAL
        return PipelineExitCode.SUCCESS

    def _status_to_run_status(self, status: PipelineExitCode) -> RunStatus:
        """Convert PipelineExitCode to RunStatus.

        Args:
            status: Pipeline exit code

        Returns:
            Corresponding RunStatus
        """
        mapping = {
            PipelineExitCode.SUCCESS: RunStatus.SUCCESS,
            PipelineExitCode.PARTIAL: RunStatus.PARTIAL,
            PipelineExitCode.FAILED: RunStatus.FAILED,
        }
        return mapping.get(status, RunStatus.FAILED)

    @staticmethod
    def _build_vilao_translator(enable_vilao: bool):
        """Construct a Vilao translator when the feature is enabled.

        Returns ``None`` when the operator has not enabled the feature or
        the configuration is incomplete — this keeps Vilao fully opt-in.
        """
        if not enable_vilao:
            return None
        try:
            from job_board_scraper.core.config import get_settings
            from job_board_scraper.llm import (
                TitleTranslator,
                VilaoClient,
                VilaoClientConfig,
            )
        except Exception:  # pragma: no cover — defensive
            logger.exception("Failed to import Vilao integration")
            return None
        settings = get_settings()
        if not settings.VILAO_ENABLED or not settings.VILAO_API_KEY:
            logger.info("Vilao requested but disabled via settings; skipping.")
            return None
        client = VilaoClient(
            VilaoClientConfig(
                api_key=settings.VILAO_API_KEY,
                base_url=settings.VILAO_BASE_URL,
                model=settings.VILAO_MODEL,
                timeout_s=settings.VILAO_TIMEOUT_S,
                rate_limit_per_min=settings.VILAO_RATE_LIMIT_PER_MIN,
                fail_threshold=settings.VILAO_FAIL_THRESHOLD,
            )
        )
        return TitleTranslator(client)


def create_pipeline() -> ScrapingPipeline:
    """Create a pipeline with all built-in adapters registered."""
    from job_board_scraper.adapters.implementations.absolute_security_adapter import (
        AbsoluteSecurityAdapter,
    )
    from job_board_scraper.adapters.implementations.caloptima_adapter import (
        CalOptimaAdapter,
    )
    from job_board_scraper.adapters.implementations.electric_power_engineers_adapter import (  # noqa: E501
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
    from job_board_scraper.adapters.implementations.northrop_adapter import (
        NorthropAdapter,
    )
    from job_board_scraper.adapters.implementations.opswat_adapter import OpswatAdapter
    from job_board_scraper.adapters.implementations.techcorp_adapter import (
        TechCorpAdapter,
    )
    from job_board_scraper.adapters.implementations.tiktok_adapter import (
        TiktokAdapter,
    )
    from job_board_scraper.adapters.implementations.vancity_adapter import (
        VancityAdapter,
    )
    from job_board_scraper.adapters.registry import registry

    adapter_types = (
        OpswatAdapter,
        VancityAdapter,
        FarmCreditCanadaAdapter,
        CalOptimaAdapter,
        IqmetrixAdapter,
        FirstWestAdapter,
        ElectricPowerEngineersAdapter,
        AbsoluteSecurityAdapter,
        TechCorpAdapter,
        TiktokAdapter,
        NorthropAdapter,
    )
    for adapter_type in adapter_types:
        try:
            adapter = adapter_type()
        except Exception:  # noqa: BLE001
            logger.exception("Failed to instantiate %s", adapter_type.__name__)
            continue
        if registry.get_or_none(adapter.slug) is None:
            registry.register(adapter)

    return ScrapingPipeline()
