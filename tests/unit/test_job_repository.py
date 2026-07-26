"""Unit tests for ``repositories/job_repository.py``."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from job_board_scraper.models.db_job import Job
from job_board_scraper.models.job import JobStatus
from job_board_scraper.repositories.job_repository import JobRepository


def _make_session(result: MagicMock | None = None) -> MagicMock:
    s = MagicMock()
    s.execute = AsyncMock(return_value=result)
    s.flush = AsyncMock()
    s.refresh = AsyncMock()
    s.add = MagicMock()
    return s


def _scalar_result(value) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


def _scalars_result(values: list) -> MagicMock:
    r = MagicMock()
    r.scalars.return_value.all.return_value = values
    return r


def _update_result(rowcount: int) -> MagicMock:
    r = MagicMock()
    r.rowcount = rowcount
    return r


class TestJobRepositoryFindByCanonicalUrl:
    @pytest.mark.asyncio
    async def test_returns_job(self) -> None:
        repo = JobRepository()
        job = MagicMock(spec=Job)
        session = _make_session(_scalar_result(job))
        result = await repo.find_by_canonical_url(session, 1, "u")
        assert result is job

    @pytest.mark.asyncio
    async def test_returns_none(self) -> None:
        repo = JobRepository()
        session = _make_session(_scalar_result(None))
        result = await repo.find_by_canonical_url(session, 1, "u")
        assert result is None


class TestJobRepositoryFindByCompany:
    @pytest.mark.asyncio
    async def test_returns_all_for_company(self) -> None:
        repo = JobRepository()
        rows = [MagicMock(spec=Job), MagicMock(spec=Job)]
        session = _make_session(_scalars_result(rows))
        result = await repo.find_by_company(session, 1)
        assert result == rows

    @pytest.mark.asyncio
    async def test_returns_filtered(self) -> None:
        repo = JobRepository()
        session = _make_session(_scalars_result([]))
        result = await repo.find_by_company(session, 1, status="open")
        assert result == []


class TestJobRepositoryUpsert:
    @pytest.mark.asyncio
    async def test_inserts_when_new(self) -> None:
        repo = JobRepository()
        job = MagicMock(spec=Job)
        job.company_id = 1
        job.canonical_url = "u"
        session = _make_session(_scalar_result(None))
        result = await repo.upsert(session, job)
        assert result is job
        session.add.assert_called_once_with(job)

    @pytest.mark.asyncio
    async def test_updates_when_existing(self) -> None:
        repo = JobRepository()
        existing = MagicMock(spec=Job)
        existing.title = "Old"
        existing.location = "Remote"
        new_job = MagicMock(spec=Job)
        new_job.company_id = 1
        new_job.canonical_url = "u"
        new_job.title = "New"
        new_job.location = "Ho Chi Minh"
        new_job.url = "https://example.com"
        new_job.date_posted = None
        new_job.status = JobStatus.open.value
        new_job.source_job_id = "src"
        new_job.raw_data = {"k": "v"}

        session = _make_session(_scalar_result(existing))
        result = await repo.upsert(session, new_job)
        assert result is existing
        assert existing.title == "New"
        assert existing.location == "Ho Chi Minh"
        session.flush.assert_awaited()


class TestJobRepositoryUpsertBatch:
    @pytest.mark.asyncio
    async def test_empty_returns_two_empty_lists(self) -> None:
        repo = JobRepository()
        session = _make_session()
        result = await repo.upsert_batch(session, [])
        assert result == ([], [])

    @pytest.mark.asyncio
    async def test_batch_creates_new(self) -> None:
        repo = JobRepository()
        a = MagicMock(spec=Job)
        a.company_id = 1
        a.canonical_url = "u1"
        b = MagicMock(spec=Job)
        b.company_id = 1
        b.canonical_url = "u2"
        session = _make_session(_scalars_result([]))
        created, updated = await repo.upsert_batch(session, [a, b])
        assert created == [a, b]
        assert updated == []

    @pytest.mark.asyncio
    async def test_batch_updates_existing(self) -> None:
        repo = JobRepository()
        existing = MagicMock(spec=Job)
        existing.canonical_url = "u1"
        existing.title = "Old"
        new_job = MagicMock(spec=Job)
        new_job.company_id = 1
        new_job.canonical_url = "u1"
        new_job.title = "New"
        new_job.location = "Remote"
        new_job.url = "u"
        new_job.date_posted = None
        new_job.status = JobStatus.open.value
        new_job.source_job_id = "src"
        new_job.raw_data = {}
        session = _make_session(_scalars_result([existing]))
        created, updated = await repo.upsert_batch(session, [new_job])
        assert created == []
        assert updated == [existing]
        assert existing.title == "New"


class TestJobRepositoryMarkStale:
    @pytest.mark.asyncio
    async def test_returns_rowcount(self) -> None:
        repo = JobRepository()
        session = _make_session(_update_result(3))
        result = await repo.mark_stale_jobs_closed(session, 1, {"u"})
        assert result == 3

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_rowcount(self) -> None:
        repo = JobRepository()
        session = _make_session(_update_result(0))
        result = await repo.mark_stale_jobs_closed(session, 1, {"u"})
        assert result == 0


class TestJobRepositoryReopen:
    @pytest.mark.asyncio
    async def test_returns_zero_when_seen_urls_empty(self) -> None:
        repo = JobRepository()
        session = _make_session()
        result = await repo.reopen_closed_jobs(session, 1, set())
        assert result == 0
        session.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_returns_rowcount(self) -> None:
        repo = JobRepository()
        session = _make_session(_update_result(2))
        result = await repo.reopen_closed_jobs(session, 1, {"u"})
        assert result == 2

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_rowcount(self) -> None:
        repo = JobRepository()
        session = _make_session(_update_result(0))
        result = await repo.reopen_closed_jobs(session, 1, {"u"})
        assert result == 0
