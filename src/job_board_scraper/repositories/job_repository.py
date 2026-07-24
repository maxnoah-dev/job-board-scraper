"""Async job repository.

Repository pattern implementation for job CRUD operations with
transactional upsert and idempotency. Uses SQLAlchemy 2 async sessions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from job_board_scraper.models.db_job import Job
from job_board_scraper.models.job import JobStatus

if TYPE_CHECKING:
    pass


class JobRepository:
    """Repository for job CRUD operations.

    Provides async methods for finding, creating, updating, and batch
    processing of job records with proper deduplication.
    """

    async def find_by_canonical_url(
        self,
        session: AsyncSession,
        company_id: int,
        canonical_url: str,
    ) -> Job | None:
        """Find a job by company and canonical URL.

        Args:
            session: The async database session.
            company_id: The company's primary key.
            canonical_url: The canonical URL for deduplication.

        Returns:
            The Job instance if found, None otherwise.
        """
        stmt = select(Job).where(
            and_(
                Job.company_id == company_id,
                Job.canonical_url == canonical_url,
            )
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_company(
        self,
        session: AsyncSession,
        company_id: int,
        status: str | None = None,
    ) -> list[Job]:
        """Find all jobs for a company, optionally filtered by status.

        Args:
            session: The async database session.
            company_id: The company's primary key.
            status: Optional status filter (e.g., "open", "closed").

        Returns:
            List of Job instances for the company.
        """
        stmt = select(Job).where(Job.company_id == company_id)
        if status is not None:
            stmt = stmt.where(Job.status == status)
        stmt = stmt.order_by(Job.created_at.desc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def upsert(
        self,
        session: AsyncSession,
        job: Job,
    ) -> Job:
        """Insert or update a single job.

        Uses canonical_url + company_id as the deduplication key.

        Args:
            session: The async database session.
            job: The Job instance to upsert.

        Returns:
            The upserted Job instance with updated id if new.
        """
        existing = await self.find_by_canonical_url(
            session,
            job.company_id,
            job.canonical_url,
        )

        if existing is not None:
            existing.title = job.title
            existing.location = job.location
            existing.url = job.url
            existing.date_posted = job.date_posted
            existing.status = job.status
            existing.source_job_id = job.source_job_id
            existing.raw_data = job.raw_data
            existing.updated_at = datetime.now(UTC)
            await session.flush()
            return existing

        session.add(job)
        await session.flush()
        await session.refresh(job)
        return job

    async def upsert_batch(
        self,
        session: AsyncSession,
        jobs: list[Job],
    ) -> tuple[list[Job], list[Job]]:
        """Insert or update multiple jobs in a batch.

        Efficiently processes a list of jobs, returning two lists:
        - created: Jobs that were newly inserted
        - updated: Jobs that were updated

        Args:
            session: The async database session.
            jobs: List of Job instances to upsert.

        Returns:
            Tuple of (created_jobs, updated_jobs).
        """
        if not jobs:
            return [], []

        created: list[Job] = []
        updated: list[Job] = []

        existing_jobs = await session.execute(
            select(Job).where(
                and_(
                    Job.company_id == jobs[0].company_id,
                    Job.canonical_url.in_([job.canonical_url for job in jobs]),
                )
            )
        )
        existing_by_url = {
            job.canonical_url: job for job in existing_jobs.scalars().all()
        }

        for job in jobs:
            existing = existing_by_url.get(job.canonical_url)

            if existing is not None:
                existing.title = job.title
                existing.location = job.location
                existing.url = job.url
                existing.date_posted = job.date_posted
                existing.status = job.status
                existing.source_job_id = job.source_job_id
                existing.raw_data = job.raw_data
                existing.updated_at = datetime.now(UTC)
                await session.flush()
                updated.append(existing)
            else:
                session.add(job)
                await session.flush()
                await session.refresh(job)
                created.append(job)

        return created, updated

    async def mark_stale_jobs_closed(
        self,
        session: AsyncSession,
        company_id: int,
        seen_urls: set[str],
    ) -> int:
        """Mark jobs as closed if they were not seen in the current scrape.

        Any job for this company with a canonical_url NOT in seen_urls
        will be marked as closed.

        Args:
            session: The async database session.
            company_id: The company's primary key.
            seen_urls: Set of canonical URLs seen in the current scrape.

        Returns:
            Number of jobs marked as closed.
        """
        stmt = (
            update(Job)
            .where(
                and_(
                    Job.company_id == company_id,
                    Job.status == JobStatus.open.value,
                    Job.canonical_url.not_in(seen_urls),
                )
            )
            .values(status=JobStatus.closed.value)
        )
        result = await session.execute(stmt)
        await session.flush()
        return result.rowcount or 0

    async def reopen_closed_jobs(
        self,
        session: AsyncSession,
        company_id: int,
        seen_urls: set[str],
    ) -> int:
        """Reopen jobs that were previously closed but are seen again.

        Any job for this company that was closed but now appears in seen_urls
        will be reopened.

        Args:
            session: The async database session.
            company_id: The company's primary key.
            seen_urls: Set of canonical URLs seen in the current scrape.

        Returns:
            Number of jobs reopened.
        """
        if not seen_urls:
            return 0

        stmt = (
            update(Job)
            .where(
                and_(
                    Job.company_id == company_id,
                    Job.status == JobStatus.closed.value,
                    Job.canonical_url.in_(seen_urls),
                )
            )
            .values(status=JobStatus.open.value)
        )
        result = await session.execute(stmt)
        await session.flush()
        return result.rowcount or 0


# Singleton instance for convenience
job_repository = JobRepository()
