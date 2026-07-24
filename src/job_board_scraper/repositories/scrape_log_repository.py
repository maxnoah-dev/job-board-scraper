"""Async scrape log repository.

Repository pattern implementation for scrape run and scrape attempt records.
Uses SQLAlchemy 2 async sessions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from job_board_scraper.models.db_scrape_attempt import ScrapeAttempt
from job_board_scraper.models.db_scrape_run import RunStatus, ScrapeRun

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# ScrapeRunRepository
# ---------------------------------------------------------------------------


class ScrapeRunRepository:
    """Repository for scrape run CRUD operations.

    Manages the lifecycle of scrape runs - creates, updates status,
    and handles orphaned run cleanup.
    """

    async def create(
        self,
        session: AsyncSession,
        triggered_by: str | None = None,
    ) -> ScrapeRun:
        """Create a new scrape run.

        Args:
            session: The async database session.
            triggered_by: Optional identifier for what triggered this run
                (e.g., "scheduler", "manual", "api").

        Returns:
            The newly created ScrapeRun instance.
        """
        run = ScrapeRun(
            status=RunStatus.RUNNING.value,
            triggered_by=triggered_by,
        )
        session.add(run)
        await session.flush()
        await session.refresh(run)
        return run

    async def find_by_id(
        self,
        session: AsyncSession,
        run_id: int,
    ) -> ScrapeRun | None:
        """Find a scrape run by its primary key.

        Args:
            session: The async database session.
            run_id: The scrape run's primary key.

        Returns:
            The ScrapeRun instance if found, None otherwise.
        """
        stmt = select(ScrapeRun).where(ScrapeRun.id == run_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_active_runs(
        self,
        session: AsyncSession,
    ) -> list[ScrapeRun]:
        """Find all runs that are currently running.

        Args:
            session: The async database session.

        Returns:
            List of ScrapeRun instances with RUNNING status.
        """
        stmt = (
            select(ScrapeRun)
            .where(ScrapeRun.status == RunStatus.RUNNING.value)
            .options(selectinload(ScrapeRun.attempts))
            .order_by(ScrapeRun.started_at.desc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(
        self,
        session: AsyncSession,
        run_id: int,
        status: str,
    ) -> bool:
        """Update the status of a scrape run.

        Args:
            session: The async database session.
            run_id: The scrape run's primary key.
            status: New status value.

        Returns:
            True if the run was updated, False if not found.
        """
        stmt = update(ScrapeRun).where(ScrapeRun.id == run_id).values(status=status)
        result = await session.execute(stmt)
        await session.flush()
        return (result.rowcount or 0) > 0

    async def mark_finished(
        self,
        session: AsyncSession,
        run_id: int,
    ) -> bool:
        """Mark a scrape run as finished by setting finished_at.

        Args:
            session: The async database session.
            run_id: The scrape run's primary key.

        Returns:
            True if the run was updated, False if not found.
        """
        stmt = (
            update(ScrapeRun)
            .where(ScrapeRun.id == run_id)
            .values(finished_at=datetime.now(UTC))
        )
        result = await session.execute(stmt)
        await session.flush()
        return (result.rowcount or 0) > 0

    async def mark_orphans_interrupted(
        self,
        session: AsyncSession,
        timeout_seconds: int = 3600,
    ) -> int:
        """Mark orphaned runs as interrupted.

        Orphaned runs are those that are still in RUNNING status
        and have exceeded the timeout threshold.

        Args:
            session: The async database session.
            timeout_seconds: Seconds after which a running run is considered
                orphaned (default: 1 hour).

        Returns:
            Number of runs marked as interrupted.
        """
        cutoff = datetime.now(UTC).replace(microsecond=0)
        cutoff = datetime.fromtimestamp(
            cutoff.timestamp() - timeout_seconds,
            tz=UTC,
        )

        stmt = (
            update(ScrapeRun)
            .where(
                and_(
                    ScrapeRun.status == RunStatus.RUNNING.value,
                    ScrapeRun.started_at < cutoff,
                )
            )
            .values(
                status=RunStatus.INTERRUPTED.value,
                finished_at=datetime.now(UTC),
            )
        )
        result = await session.execute(stmt)
        await session.flush()
        return result.rowcount or 0


# ---------------------------------------------------------------------------
# ScrapeAttemptRepository
# ---------------------------------------------------------------------------


class ScrapeAttemptRepository:
    """Repository for scrape attempt CRUD operations.

    Manages per-company metrics for a single scrape run.
    """

    async def create(
        self,
        session: AsyncSession,
        run_id: int,
        company_id: int,
    ) -> ScrapeAttempt:
        """Create a new scrape attempt for a run-company pair.

        Args:
            session: The async database session.
            run_id: The parent scrape run's primary key.
            company_id: The company being scraped.

        Returns:
            The newly created ScrapeAttempt instance.
        """
        attempt = ScrapeAttempt(
            run_id=run_id,
            company_id=company_id,
        )
        session.add(attempt)
        await session.flush()
        await session.refresh(attempt)
        return attempt

    async def find_by_run(
        self,
        session: AsyncSession,
        run_id: int,
    ) -> list[ScrapeAttempt]:
        """Find all attempts for a specific scrape run.

        Args:
            session: The async database session.
            run_id: The scrape run's primary key.

        Returns:
            List of ScrapeAttempt instances for the run.
        """
        stmt = (
            select(ScrapeAttempt)
            .where(ScrapeAttempt.run_id == run_id)
            .options(
                selectinload(ScrapeAttempt.company),
            )
            .order_by(ScrapeAttempt.started_at)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def find_by_company(
        self,
        session: AsyncSession,
        company_id: int,
    ) -> list[ScrapeAttempt]:
        """Find all attempts for a specific company.

        Args:
            session: The async database session.
            company_id: The company's primary key.

        Returns:
            List of ScrapeAttempt instances for the company.
        """
        stmt = (
            select(ScrapeAttempt)
            .where(ScrapeAttempt.company_id == company_id)
            .options(selectinload(ScrapeAttempt.run))
            .order_by(ScrapeAttempt.started_at.desc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def update(
        self,
        session: AsyncSession,
        attempt_id: int,
        **kwargs: object,
    ) -> ScrapeAttempt | None:
        """Update a scrape attempt with the given fields.

        Args:
            session: The async database session.
            attempt_id: The scrape attempt's primary key.
            **kwargs: Fields to update (e.g., status, jobs_found, error_message).

        Returns:
            The updated ScrapeAttempt instance, or None if not found.
        """
        if not kwargs:
            stmt = select(ScrapeAttempt).where(ScrapeAttempt.id == attempt_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

        stmt = (
            update(ScrapeAttempt).where(ScrapeAttempt.id == attempt_id).values(**kwargs)
        )
        await session.execute(stmt)
        await session.flush()

        stmt = select(ScrapeAttempt).where(ScrapeAttempt.id == attempt_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_complete(
        self,
        session: AsyncSession,
        attempt_id: int,
        status: str,
    ) -> bool:
        """Mark a scrape attempt as complete.

        Sets the finished_at timestamp and status.

        Args:
            session: The async database session.
            attempt_id: The scrape attempt's primary key.
            status: Final status (e.g., "success", "failed", "partial").

        Returns:
            True if the attempt was updated, False if not found.
        """
        stmt = (
            update(ScrapeAttempt)
            .where(ScrapeAttempt.id == attempt_id)
            .values(
                finished_at=datetime.now(UTC),
                status=status,
            )
        )
        result = await session.execute(stmt)
        await session.flush()
        return (result.rowcount or 0) > 0


# Singleton instances for convenience
scrape_run_repository = ScrapeRunRepository()
scrape_attempt_repository = ScrapeAttemptRepository()
