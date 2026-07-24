"""Repository pattern implementations for async database operations.

This package provides repository classes for CRUD operations on:
- Companies: CompanyRepository
- Jobs: JobRepository
- Scrape runs: ScrapeRunRepository
- Scrape attempts: ScrapeAttemptRepository

All repositories use SQLAlchemy 2 async sessions with proper relationship loading.
"""

from __future__ import annotations

from job_board_scraper.repositories.company_repository import (
    CompanyRepository,
    company_repository,
)
from job_board_scraper.repositories.job_repository import (
    JobRepository,
    job_repository,
)
from job_board_scraper.repositories.scrape_log_repository import (
    ScrapeAttemptRepository,
    ScrapeRunRepository,
    scrape_attempt_repository,
    scrape_run_repository,
)

__all__ = [
    # Company repository
    "CompanyRepository",
    "company_repository",
    # Job repository
    "JobRepository",
    "job_repository",
    # Scrape run repository
    "ScrapeRunRepository",
    "scrape_run_repository",
    # Scrape attempt repository
    "ScrapeAttemptRepository",
    "scrape_attempt_repository",
]
