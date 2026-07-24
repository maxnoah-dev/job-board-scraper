"""Scrape run domain model.

SQLAlchemy 2 async model for scrape_runs table.
One row per pipeline invocation (manual or scheduled).
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

if TYPE_CHECKING:
    from job_board_scraper.core.base import Base
else:
    from job_board_scraper.core.base import Base  # noqa: E402


class RunStatus(str, enum.Enum):
    """Status of a scrape run."""

    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


class ScrapeRun(Base):
    """SQLAlchemy model for scrape_runs table.

    Represents a single invocation of the ETL pipeline.
    One run can contain multiple attempts (one per company).
    """

    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
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
        default=RunStatus.RUNNING.value,
        nullable=False,
    )
    triggered_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    @property
    def duration_seconds(self) -> float | None:
        """Calculate run duration in seconds."""
        if self.finished_at and self.started_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None

    def __repr__(self) -> str:
        return f"<ScrapeRun(id={self.id}, status={self.status!r}, started_at={self.started_at!r})>"
