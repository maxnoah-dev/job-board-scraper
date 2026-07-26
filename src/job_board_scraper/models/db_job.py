"""Job domain model for database storage.

SQLAlchemy 2 async model for the jobs table with unique constraint on
(company_id, canonical_url) for deduplication.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from job_board_scraper.core.base import Base
else:
    from job_board_scraper.core.base import Base  # noqa: E402


class Job(Base):
    """SQLAlchemy model for jobs table.

    Unique constraint on (company_id, canonical_url) per ADR-0003.
    This ensures one job URL per company without cross-company dedupe.
    """

    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "canonical_url", name="uq_jobs_company_canonical_url"
        ),
        Index("idx_jobs_company_id", "company_id"),
        Index("idx_jobs_status", "status"),
        Index("idx_jobs_date_posted", "date_posted"),
        Index("idx_jobs_canonical_url", "canonical_url"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id"), nullable=False
    )
    company: Mapped[Company] = relationship(  # noqa: F821
        "Company", back_populates="jobs", lazy="selectin"
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    title_vi: Mapped[str | None] = mapped_column(String(500), nullable=True)
    location: Mapped[str] = mapped_column(String(255), default="Remote", nullable=False)
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    canonical_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    date_posted: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    source_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    salary_raw: Mapped[str | None] = mapped_column(String(200), nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Job(id={self.id}, title={self.title!r}, status={self.status!r})>"
