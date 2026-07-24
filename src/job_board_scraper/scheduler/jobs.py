"""Scheduler jobs module.

Idempotent scripts and APScheduler integration for local/single-process scheduling.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class ScheduleType(Enum):
    """Type of scheduling."""

    CRON = "cron"
    INTERVAL = "interval"
    ONE_SHOT = "one_shot"


@dataclass
class ScrapeJob:
    """A scheduled scrape job."""

    job_id: str
    schedule_type: ScheduleType
    companies: list[str]  # Empty means all companies
    enabled: bool = True
    last_run: datetime | None = None
    next_run: datetime | None = None
    cron_expr: str | None = None
    interval_seconds: int | None = None


class JobScheduler:
    """APScheduler wrapper for job scheduling."""

    def __init__(self) -> None:
        self._jobs: dict[str, ScrapeJob] = {}
        self._running = False

    def add_job(
        self,
        job_id: str,
        schedule_type: ScheduleType,
        companies: list[str] | None = None,
        cron_expr: str | None = None,
        interval_seconds: int | None = None,
    ) -> ScrapeJob:
        """Add a scrape job to the schedule."""
        job = ScrapeJob(
            job_id=job_id,
            schedule_type=schedule_type,
            companies=companies or [],
            cron_expr=cron_expr,
            interval_seconds=interval_seconds,
        )
        self._jobs[job_id] = job
        return job

    def remove_job(self, job_id: str) -> bool:
        """Remove a job from the schedule."""
        return self._jobs.pop(job_id, None) is not None

    def get_job(self, job_id: str) -> ScrapeJob | None:
        """Get a job by ID."""
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[ScrapeJob]:
        """List all scheduled jobs."""
        return list(self._jobs.values())

    def enable_job(self, job_id: str) -> bool:
        """Enable a job."""
        job = self._jobs.get(job_id)
        if job:
            job.enabled = True
            return True
        return False

    def disable_job(self, job_id: str) -> bool:
        """Disable a job."""
        job = self._jobs.get(job_id)
        if job:
            job.enabled = False
            return True
        return False

    async def run_job(self, job_id: str) -> bool:
        """Manually trigger a job run."""
        job = self._jobs.get(job_id)
        if not job:
            return False

        job.last_run = datetime.now(UTC)
        # Actual scraping would be triggered here
        return True


# Global scheduler instance
_scheduler: JobScheduler | None = None


def get_scheduler() -> JobScheduler:
    """Get or create the global scheduler."""
    global _scheduler
    if _scheduler is None:
        _scheduler = JobScheduler()
    return _scheduler
