"""Scrape attempt domain model.

SQLAlchemy 2 async model for scrape_attempts table.
One row per (run, company) combination.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

if TYPE_CHECKING:
    from job_board_scraper.core.base import Base
else:
    from job_board_scraper.core.base import Base  # noqa: E402


class AttemptStatus(str, enum.Enum):
    """Status of a single scrape attempt for a company."""

    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


class ScrapeAttempt(Base):
    """SQLAlchemy model for scrape_attempts table.

    Tracks per-company metrics for a single scrape run.
    Contains completeness and authority flags for stale reconciliation.
    """

    __tablename__ = "scrape_attempts"
    __table_args__ = (
        Index("idx_attempts_run_id", "run_id"),
        Index("idx_attempts_company_id", "company_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("scrape_runs.id"), nullable=False
    )
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=AttemptStatus.RUNNING.value,
        nullable=False,
    )
    jobs_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_rejected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    new_jobs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    closed_jobs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    missing_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pages_fetched: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    requests_made: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    authoritative_snapshot: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    error_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    warnings: Mapped[str | None] = mapped_column(Text, nullable=True)

    @property
    def duration_seconds(self) -> float | None:
        """Calculate attempt duration in seconds."""
        if self.finished_at and self.started_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None

    def __repr__(self) -> str:
        return (
            f"<ScrapeAttempt(id={self.id}, company_id={self.company_id}, "
            f"status={self.status!r}, jobs_found={self.jobs_found})>"
        )
