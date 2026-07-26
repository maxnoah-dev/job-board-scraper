"""Add title_vi and salary_raw to jobs table

Revision ID: 002_add_title_vi_salary
Revises: 001_initial_schema_a1b2c3d4
Create Date: 2026-07-26 20:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "002_add_title_vi_salary"
down_revision: Union[str, None] = "001_initial_schema_a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add ``title_vi`` and ``salary_raw`` columns to the ``jobs`` table."""
    op.add_column(
        "jobs",
        sa.Column("title_vi", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "jobs",
        sa.Column("salary_raw", sa.String(length=200), nullable=True),
    )


def downgrade() -> None:
    """Remove ``title_vi`` and ``salary_raw`` columns from the ``jobs`` table."""
    op.drop_column("jobs", "salary_raw")
    op.drop_column("jobs", "title_vi")
