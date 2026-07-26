"""Unit tests for ``repositories/company_repository.py``."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from job_board_scraper.models.db_company import Company
from job_board_scraper.repositories.company_repository import CompanyRepository


def _make_session_with_result(result: MagicMock) -> AsyncMock:
    """Build an AsyncSession whose ``await session.execute(...)`` resolves to ``result``."""
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.merge = AsyncMock()
    return session


def _scalar_result(value) -> MagicMock:
    """Result mock for ``scalar_one_or_none`` style queries."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _scalars_result(values: list) -> MagicMock:
    """Result mock for ``scalars().all()`` style queries."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


class TestCompanyRepositoryFindById:
    @pytest.mark.asyncio
    async def test_returns_company_when_found(self) -> None:
        repo = CompanyRepository()
        company = MagicMock(spec=Company)
        session = _make_session_with_result(_scalar_result(company))
        result = await repo.find_by_id(session, 1)
        assert result is company

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self) -> None:
        repo = CompanyRepository()
        session = _make_session_with_result(_scalar_result(None))
        result = await repo.find_by_id(session, 999)
        assert result is None


class TestCompanyRepositoryFindBySlug:
    @pytest.mark.asyncio
    async def test_returns_company_by_slug(self) -> None:
        repo = CompanyRepository()
        company = MagicMock(spec=Company)
        session = _make_session_with_result(_scalar_result(company))
        result = await repo.find_by_slug(session, "opswat")
        assert result is company

    @pytest.mark.asyncio
    async def test_returns_none_when_missing(self) -> None:
        repo = CompanyRepository()
        session = _make_session_with_result(_scalar_result(None))
        result = await repo.find_by_slug(session, "missing")
        assert result is None


class TestCompanyRepositoryFindActive:
    @pytest.mark.asyncio
    async def test_returns_active_companies(self) -> None:
        repo = CompanyRepository()
        rows = [MagicMock(spec=Company), MagicMock(spec=Company)]
        session = _make_session_with_result(_scalars_result(rows))
        result = await repo.find_active(session)
        assert result == rows


class TestCompanyRepositoryUpsert:
    @pytest.mark.asyncio
    async def test_upsert_inserts_when_no_id(self) -> None:
        repo = CompanyRepository()
        company = MagicMock(spec=Company)
        company.id = None
        session = _make_session_with_result(_scalar_result(None))
        result = await repo.upsert(session, company)
        assert result is company
        session.add.assert_called_once_with(company)
        session.flush.assert_awaited()
        session.refresh.assert_awaited_with(company)

    @pytest.mark.asyncio
    async def test_upsert_updates_when_has_id(self) -> None:
        repo = CompanyRepository()
        company = MagicMock(spec=Company)
        company.id = 5
        merged = MagicMock(spec=Company)
        session = _make_session_with_result(_scalar_result(None))
        session.merge = AsyncMock(return_value=merged)
        result = await repo.upsert(session, company)
        assert result is merged
        session.merge.assert_awaited_with(company)


class TestCompanyRepositoryDeactivate:
    @pytest.mark.asyncio
    async def test_deactivate_returns_false_when_missing(self) -> None:
        repo = CompanyRepository()
        session = _make_session_with_result(_scalar_result(None))
        assert await repo.deactivate(session, 999) is False

    @pytest.mark.asyncio
    async def test_deactivate_returns_true_when_found(self) -> None:
        repo = CompanyRepository()
        company = MagicMock(spec=Company)
        company.is_active = True
        session = _make_session_with_result(_scalar_result(company))
        result = await repo.deactivate(session, 1)
        assert result is True
        assert company.is_active is False
        session.flush.assert_awaited()
