"""Alembic migration environment.

This env.py is configured for SQLAlchemy 2 with support for both
SQLite (aiosqlite) and PostgreSQL (asyncpg) databases.
Supports both offline (sqlmigrate-like) and online modes.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context

# Add src directory to Python path so imports work
SRC_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection

from job_board_scraper.core.database import Base
from job_board_scraper.models.db_company import Company  # noqa: F401
from job_board_scraper.models.db_job import Job  # noqa: F401
from job_board_scraper.models.db_scrape_run import ScrapeRun  # noqa: F401
from job_board_scraper.models.db_scrape_attempt import ScrapeAttempt  # noqa: F401

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata


def get_url() -> str:
    """Get database URL from environment variable or config.

    Supports:
    - SQLite: sqlite:///./data/jobs.db
    - PostgreSQL: postgresql+psycopg2://user:pass@host/db

    For migrations, we use the synchronous driver.
    """
    import os

    database_url = os.environ.get(
        "DATABASE_URL",
        "sqlite:///./data/jobs.db",
    )

    # Convert async URL to sync URL for Alembic
    # sqlite+aiosqlite -> sqlite
    # postgresql+asyncpg -> postgresql+psycopg2
    if "+aiosqlite" in database_url:
        return database_url.replace("+aiosqlite", "")
    elif "+asyncpg" in database_url:
        return database_url.replace("+asyncpg", "+psycopg2")

    return database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_as_batch=True,  # Required for SQLite to handle ALTER TABLE
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=True,  # Required for SQLite to handle ALTER TABLE
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
