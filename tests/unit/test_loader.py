"""Unit tests for ``etl/loader.py``."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from job_board_scraper.etl.loader import Loader, create_loader
from job_board_scraper.models.db_scrape_attempt import AttemptStatus
from job_board_scraper.models.job import JobRecord, JobStatus


def _record() -> JobRecord:
    return JobRecord(
        source_company_id="opswat",
        title="Senior Engineer",
        url="https://example.com/1",
        canonical_url="https://example.com/1",
        company_id=1,
        status=JobStatus.open,
    )


@pytest.mark.asyncio
class TestLoadJobs:
    async def test_load_empty(self) -> None:
        loader = Loader()
        session = MagicMock()
        created, updated = await loader.load_jobs(session, [], company_id=1)
        assert created == []
        assert updated == []

    async def test_load_records_upserts(self) -> None:
        loader = Loader()
        session = MagicMock()
        loader._repo.upsert_batch = AsyncMock(return_value=([MagicMock()], [MagicMock()]))
        created, updated = await loader.load_jobs(session, [_record()], company_id=1)
        assert len(created) == 1
        assert len(updated) == 1


@pytest.mark.asyncio
class TestRecordAttempt:
    async def test_record_attempt_start(self) -> None:
        loader = Loader()
        session = MagicMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        attempt = await loader.record_attempt_start(session, run_id=1, company_id=1)
        assert attempt.status == AttemptStatus.RUNNING.value
        assert session.add.called

    async def test_record_attempt_success(self) -> None:
        loader = Loader()
        session = MagicMock()
        session.flush = AsyncMock()
        attempt = MagicMock()
        await loader.record_attempt_success(
            session,
            attempt,
            jobs_found=10,
            new_jobs=3,
            closed_jobs=1,
            records_rejected=2,
            warnings="warn",
        )
        assert attempt.status == AttemptStatus.SUCCESS.value
        assert attempt.complete is True

    async def test_record_attempt_failure(self) -> None:
        loader = Loader()
        session = MagicMock()
        session.flush = AsyncMock()
        attempt = MagicMock()
        await loader.record_attempt_failure(
            session, attempt, error_type="X", error_message="boom", partial=False
        )
        assert attempt.status == AttemptStatus.FAILED.value

    async def test_record_attempt_failure_partial(self) -> None:
        loader = Loader()
        session = MagicMock()
        session.flush = AsyncMock()
        attempt = MagicMock()
        await loader.record_attempt_failure(
            session, attempt, error_type="X", error_message="boom", partial=True
        )
        assert attempt.status == AttemptStatus.PARTIAL.value


@pytest.mark.asyncio
class TestStaleReconciliation:
    async def test_close_stale_jobs(self) -> None:
        loader = Loader()
        session = MagicMock()
        loader._repo.mark_stale_jobs_closed = AsyncMock(return_value=4)
        count = await loader.close_stale_jobs(session, company_id=1, seen_urls=set())
        assert count == 4

    async def test_reopen_closed_jobs(self) -> None:
        loader = Loader()
        session = MagicMock()
        loader._repo.reopen_closed_jobs = AsyncMock(return_value=2)
        count = await loader.reopen_closed_jobs(session, company_id=1, seen_urls=set())
        assert count == 2


class TestRecordToJob:
    def test_record_to_job_with_enum_status(self) -> None:
        loader = Loader()
        job = loader._record_to_job(_record())
        assert job.company_id == 1
        assert job.title == "Senior Engineer"
        assert job.status == "open"


def test_create_loader() -> None:
    assert isinstance(create_loader(), Loader)
