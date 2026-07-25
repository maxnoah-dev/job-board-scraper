"""Company domain model.

Pydantic v2 schema for a company with its adapter type, base URL, and
per-source configuration.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from job_board_scraper.core.base import Base
else:
    # Runtime import after class definition to avoid circular import
    from job_board_scraper.core.base import Base  # noqa: E402, I100


class AdapterType(str, enum.Enum):
    """Type of adapter used to scrape this company."""

    API = "api"  # API/ATS integration (Greenhouse, Workday, etc.)
    HTML = "html"  # Static HTML scraping
    BROWSER = "browser"  # Anti-bot sites requiring Playwright


class Company(Base):
    """SQLAlchemy model for companies table.

    Represents a job source (company) with its scraping configuration.
    """

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    adapter_type: Mapped[str] = mapped_column(String(20), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    authoritative: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
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

    jobs: Mapped[list["Job"]] = relationship(  # noqa: F821
        "Job", back_populates="company", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Company(id={self.id}, slug={self.slug!r}, adapter_type={self.adapter_type})>"
