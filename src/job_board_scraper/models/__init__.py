"""Domain models package."""

from job_board_scraper.models.db_company import AdapterType, Company
from job_board_scraper.models.db_job import Job
from job_board_scraper.models.db_scrape_attempt import AttemptStatus, ScrapeAttempt
from job_board_scraper.models.db_scrape_run import RunStatus, ScrapeRun
from job_board_scraper.models.job import (
    JobRecord,
    JobStatus,
    RawJobData,
    canonicalize_url,
)

__all__ = [
    # Pydantic models
    "JobRecord",
    "JobStatus",
    "RawJobData",
    "canonicalize_url",
    # SQLAlchemy models
    "AdapterType",
    "Company",
    "Job",
    "RunStatus",
    "ScrapeRun",
    "AttemptStatus",
    "ScrapeAttempt",
]
