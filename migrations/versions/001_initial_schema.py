"""Initial schema - companies, jobs, scrape_runs, scrape_attempts

Revision ID: 001_initial_schema_a1b2c3d4
Revises:
Create Date: 2026-07-24 14:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001_initial_schema_a1b2c3d4"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create companies table
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("adapter_type", sa.String(length=20), nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=False),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("authoritative", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("idx_companies_slug", "companies", ["slug"], unique=True)

    # Create scrape_runs table (no FK dependencies)
    op.create_table(
        "scrape_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="'running'"
        ),
        sa.Column("triggered_by", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create jobs table with unique constraint inline
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column(
            "location", sa.String(length=255), nullable=False, server_default="'Remote'"
        ),
        sa.Column("url", sa.String(length=2000), nullable=False),
        sa.Column("canonical_url", sa.String(length=2000), nullable=False),
        sa.Column("date_posted", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="'open'"
        ),
        sa.Column("source_job_id", sa.String(length=255), nullable=True),
        # Use JSON type that works with both SQLite and PostgreSQL
        # PostgreSQL will store as JSONB automatically
        sa.Column("raw_data", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
        # Unique constraint inline for SQLite compatibility
        sa.UniqueConstraint(
            "company_id", "canonical_url", name="uq_jobs_company_canonical_url"
        ),
    )

    # Create indexes on jobs table
    op.create_index("idx_jobs_company_id", "jobs", ["company_id"])
    op.create_index("idx_jobs_status", "jobs", ["status"])
    op.create_index("idx_jobs_date_posted", "jobs", ["date_posted"])
    op.create_index("idx_jobs_canonical_url", "jobs", ["canonical_url"])

    # Create scrape_attempts table
    op.create_table(
        "scrape_attempts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="'running'"
        ),
        sa.Column("jobs_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_rejected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_jobs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("closed_jobs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("missing_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pages_fetched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("requests_made", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("complete", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column(
            "authoritative_snapshot",
            sa.Boolean(),
            nullable=False,
            server_default="1",
        ),
        sa.Column("error_type", sa.String(length=50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("warnings", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["scrape_runs.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes on scrape_attempts table
    op.create_index("idx_attempts_run_id", "scrape_attempts", ["run_id"])
    op.create_index("idx_attempts_company_id", "scrape_attempts", ["company_id"])


def downgrade() -> None:
    # Drop scrape_attempts table
    op.drop_index("idx_attempts_company_id", table_name="scrape_attempts")
    op.drop_index("idx_attempts_run_id", table_name="scrape_attempts")
    op.drop_table("scrape_attempts")

    # Drop jobs table indexes and constraints
    op.drop_constraint("uq_jobs_company_canonical_url", "jobs", type_="unique")
    op.drop_index("idx_jobs_canonical_url", table_name="jobs")
    op.drop_index("idx_jobs_date_posted", table_name="jobs")
    op.drop_index("idx_jobs_status", table_name="jobs")
    op.drop_index("idx_jobs_company_id", table_name="jobs")
    op.drop_table("jobs")

    # Drop scrape_runs table
    op.drop_table("scrape_runs")

    # Drop companies table
    op.drop_index("idx_companies_slug", table_name="companies")
    op.drop_table("companies")
