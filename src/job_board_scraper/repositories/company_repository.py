"""Async company repository.

Repository pattern implementation for company CRUD operations.
Uses SQLAlchemy 2 async sessions with proper relationship loading.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from job_board_scraper.models.db_company import Company


class CompanyRepository:
    """Repository for company CRUD operations.

    Provides async methods for finding, creating, updating, and deactivating
    company records in the database.
    """

    async def find_by_id(
        self,
        session: AsyncSession,
        company_id: int,
    ) -> Company | None:
        """Find a company by its primary key.

        Args:
            session: The async database session.
            company_id: The company's primary key.

        Returns:
            The Company instance if found, None otherwise.
        """
        stmt = select(Company).where(Company.id == company_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_by_slug(
        self,
        session: AsyncSession,
        slug: str,
    ) -> Company | None:
        """Find a company by its unique slug.

        Args:
            session: The async database session.
            slug: The company's unique slug identifier.

        Returns:
            The Company instance if found, None otherwise.
        """
        stmt = select(Company).where(Company.slug == slug)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_active(
        self,
        session: AsyncSession,
    ) -> list[Company]:
        """Find all active companies.

        Args:
            session: The async database session.

        Returns:
            List of active Company instances.
        """
        stmt = select(Company).where(Company.is_active == True).order_by(Company.name)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def upsert(
        self,
        session: AsyncSession,
        company: Company,
    ) -> Company:
        """Insert or update a company.

        If the company has an id, updates the existing record.
        Otherwise, inserts a new record.

        Args:
            session: The async database session.
            company: The Company instance to upsert.

        Returns:
            The upserted Company instance with updated id if new.
        """
        if company.id is None:
            session.add(company)
            await session.flush()
            await session.refresh(company)
        else:
            merged = await session.merge(company)
            await session.flush()
            return merged
        return company

    async def deactivate(
        self,
        session: AsyncSession,
        company_id: int,
    ) -> bool:
        """Deactivate a company by setting is_active to False.

        Args:
            session: The async database session.
            company_id: The company's primary key.

        Returns:
            True if a company was deactivated, False if not found.
        """
        stmt = select(Company).where(Company.id == company_id).with_for_update()
        result = await session.execute(stmt)
        company = result.scalar_one_or_none()

        if company is None:
            return False

        company.is_active = False
        await session.flush()
        return True


# Singleton instance for convenience
company_repository = CompanyRepository()
