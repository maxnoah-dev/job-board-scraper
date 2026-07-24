"""Database connection management.

SQLAlchemy 2 async engine for SQLite (local/test) and PostgreSQL (production).
Connection pooling, session factory, and transaction helpers.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

# Import Base from base.py for model inheritance
from job_board_scraper.core.base import Base  # noqa: F401

# Database URL from environment
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./data/jobs.db",
)

# Global engine and session factory (initialized on startup)
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Get or create the async engine."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            DATABASE_URL,
            echo=os.environ.get("SQLALCHEMY_ECHO", "false").lower() == "true",
            poolclass=NullPool if "sqlite" in DATABASE_URL else None,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the async session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI/Starlette to get a database session."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for a single database session with commit/rollback.

    Usage:
        async with session_scope() as session:
            await session.execute(...)
            # commits on successful exit, rolls back on exception
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def transactional_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for a transaction with explicit control.

    Unlike session_scope, this doesn't auto-commit. Caller controls commit.

    Usage:
        async with transactional_session() as session:
            await session.execute(...)
            await session.commit()
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


async def init_db() -> None:
    """Initialize the database: create all tables."""
    from job_board_scraper.models import (
        db_company,  # noqa: F401
        db_job,  # noqa: F401
        db_scrape_attempt,  # noqa: F401
        db_scrape_run,  # noqa: F401
    )

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


async def check_connection() -> bool:
    """Verify database connectivity."""
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
