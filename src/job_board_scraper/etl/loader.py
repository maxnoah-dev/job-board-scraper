"""ETL loader module.

Handles database operations: transactional batch upsert, closing stale jobs,
and recording attempt metrics.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from job_board_scraper.models.db_job import Job
from job_board_scraper.models.db_scrape_attempt import AttemptStatus, ScrapeAttempt
from job_board_scraper.models.job import JobRecord, JobStatus
from job_board_scraper.repositories.job_repository import JobRepository

if TYPE_CHECKING:
    from collections.abc import Set

logger = logging.getLogger(__name__)


class Loader:
    """Handles database operations for the ETL pipeline.

    Provides transactional batch upsert, stale job reconciliation, and
    scrape attempt recording.
    """

    def __init__(self) -> None:
        self._repo = JobRepository()

    async def load_jobs(
        self,
        session: AsyncSession,
        records: list[JobRecord],
        company_id: int,
    ) -> tuple[list[Job], list[Job]]:
        """Load job records into the database.

        Args:
            session: Database session
            records: Transformed job records to upsert
            company_id: Company ID for these jobs

        Returns:
            Tuple of (created_jobs, updated_jobs)
        """
        if not records:
            return [], []

        db_jobs = [self._record_to_job(record) for record in records]
        created, updated = await self._repo.upsert_batch(session, db_jobs)

        logger.info(
            "Jobs loaded",
            extra={
                "company_id": company_id,
                "created": len(created),
                "updated": len(updated),
            },
        )

        return created, updated

    async def record_attempt_start(
        self,
        session: AsyncSession,
        run_id: int,
        company_id: int,
    ) -> ScrapeAttempt:
        """Record the start of a scrape attempt.

        Args:
            session: Database session
            run_id: Parent scrape run ID
            company_id: Company being scraped

        Returns:
            The created ScrapeAttempt record
        """
        attempt = ScrapeAttempt(
            run_id=run_id,
            company_id=company_id,
            status=AttemptStatus.RUNNING.value,
            started_at=datetime.now(UTC),
        )
        session.add(attempt)
        await session.flush()
        await session.refresh(attempt)
        return attempt

    async def record_attempt_success(
        self,
        session: AsyncSession,
        attempt: ScrapeAttempt,
        jobs_found: int,
        new_jobs: int,
        closed_jobs: int,
        records_rejected: int = 0,
        pages_fetched: int = 0,
        requests_made: int = 0,
        warnings: str | None = None,
    ) -> None:
        """Record a successful scrape attempt.

        Args:
            session: Database session
            attempt: The attempt record to update
            jobs_found: Total jobs found in this scrape
            new_jobs: Number of newly created jobs
            closed_jobs: Number of jobs closed
            records_rejected: Number of records rejected during transform
            pages_fetched: Number of pages fetched
            requests_made: Total HTTP requests made
            warnings: Any warnings from the scrape
        """
        attempt.status = AttemptStatus.SUCCESS.value
        attempt.finished_at = datetime.now(UTC)
        attempt.jobs_found = jobs_found
        attempt.new_jobs = new_jobs
        attempt.closed_jobs = closed_jobs
        attempt.records_rejected = records_rejected
        attempt.pages_fetched = pages_fetched
        attempt.requests_made = requests_made
        attempt.complete = True
        attempt.warnings = warnings
        await session.flush()

    async def record_attempt_failure(
        self,
        session: AsyncSession,
        attempt: ScrapeAttempt,
        error_type: str,
        error_message: str,
        partial: bool = False,
    ) -> None:
        """Record a failed scrape attempt.

        Args:
            session: Database session
            attempt: The attempt record to update
            error_type: Type/category of error
            error_message: Human-readable error message
            partial: Whether this was a partial failure
        """
        attempt.status = (
            AttemptStatus.PARTIAL.value if partial else AttemptStatus.FAILED.value
        )
        attempt.finished_at = datetime.now(UTC)
        attempt.error_type = error_type
        attempt.error_message = error_message
        await session.flush()

    async def close_stale_jobs(
        self,
        session: AsyncSession,
        company_id: int,
        seen_urls: Set[str],
    ) -> int:
        """Close jobs that were not seen in the current scrape.

        Args:
            session: Database session
            company_id: Company to reconcile
            seen_urls: URLs seen in current scrape

        Returns:
            Number of jobs closed
        """
        count = await self._repo.mark_stale_jobs_closed(session, company_id, seen_urls)
        logger.info(
            "Stale jobs closed", extra={"company_id": company_id, "count": count}
        )
        return count

    async def reopen_closed_jobs(
        self,
        session: AsyncSession,
        company_id: int,
        seen_urls: Set[str],
    ) -> int:
        """Reopen jobs that were previously closed but are seen again.

        Args:
            session: Database session
            company_id: Company to reconcile
            seen_urls: URLs seen in current scrape

        Returns:
            Number of jobs reopened
        """
        count = await self._repo.reopen_closed_jobs(session, company_id, seen_urls)
        logger.info(
            "Closed jobs reopened", extra={"company_id": company_id, "count": count}
        )
        return count

    def _record_to_job(self, record: JobRecord) -> Job:
        """Convert a JobRecord Pydantic model to a Job ORM object.

        Args:
            record: The validated job record

        Returns:
            Job ORM object ready for database insertion
        """
        job = Job(
            company_id=record.company_id,
            title=record.title,
            location=record.location,
            url=record.url,
            canonical_url=record.canonical_url,
            date_posted=record.date_posted,
            status=record.status.value
            if isinstance(record.status, JobStatus)
            else record.status,
            source_job_id=record.source_job_id,
            raw_data=record.raw_data,
        )
        return job


def create_loader() -> Loader:
    """Factory function to create a loader."""
    return Loader()
