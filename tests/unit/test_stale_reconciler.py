"""Unit tests for ``etl/stale_reconciler.py``."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from job_board_scraper.etl.stale_reconciler import MISSING_THRESHOLD, StaleReconciler
from job_board_scraper.models.job import JobStatus


class _FakeJob:
    """Lightweight stand-in for an ORM ``Job`` used by the reconciler."""

    def __init__(
        self,
        canonical_url: str,
        status: str = JobStatus.open.value,
        missing_count: int = 0,
    ) -> None:
        self.canonical_url = canonical_url
        self.status = status
        self.missing_count = missing_count
        self.updated_at = None


class _FakeResult:
    def __init__(self, items: list[_FakeJob]) -> None:
        self._items = items

    def scalars(self) -> _FakeResult:
        return self

    def all(self) -> list[_FakeJob]:
        return list(self._items)


class _FakeSession:
    def __init__(self, results: list[_FakeResult]) -> None:
        self._results = list(results)
        self.execute = AsyncMock(side_effect=self._execute)

    async def _execute(self, *args: object, **kwargs: object) -> _FakeResult:
        return self._results.pop(0)


@pytest.mark.asyncio
class TestStaleReconciler:
    async def test_skips_when_not_complete(self) -> None:
        session = _FakeSession([])
        reconciler = StaleReconciler()
        result = await reconciler.reconcile(
            session, 1, seen_urls=set(), is_complete=False, is_authoritative=True
        )
        assert result == {"closed": 0, "reopened": 0, "updated": 0}
        assert session.execute.await_count == 0

    async def test_skips_when_not_authoritative(self) -> None:
        session = _FakeSession([])
        reconciler = StaleReconciler()
        result = await reconciler.reconcile(
            session, 1, seen_urls=set(), is_complete=True, is_authoritative=False
        )
        assert result == {"closed": 0, "reopened": 0, "updated": 0}

    async def test_reopens_seen_closed_job(self) -> None:
        # First query: existing open jobs (none).
        # Second query: closed jobs that reappeared.
        # Third query: stale jobs after the reopen.
        seen = ["https://a.com/1"]
        job_closed = _FakeJob("https://a.com/1", status=JobStatus.closed.value)
        session = _FakeSession(
            [
                _FakeResult([]),  # open jobs (none)
                _FakeResult([job_closed]),  # closed jobs to reopen
                _FakeResult([]),  # open jobs after reopen (none)
            ]
        )
        reconciler = StaleReconciler()
        result = await reconciler.reconcile(
            session, 1, seen_urls=set(seen), is_complete=True, is_authoritative=True
        )
        assert result["reopened"] == 1
        assert job_closed.status == JobStatus.open.value

    async def test_closes_jobs_above_threshold(self) -> None:
        # First query: open jobs (one stale).
        # Second query: closed jobs (none).
        # Third query: open jobs to close if stale.
        job_stale = _FakeJob(
            "https://a.com/stale",
            status=JobStatus.open.value,
            missing_count=MISSING_THRESHOLD,  # already at threshold
        )
        session = _FakeSession(
            [
                _FakeResult([job_stale]),
                _FakeResult([]),
                _FakeResult([job_stale]),
            ]
        )
        reconciler = StaleReconciler()
        result = await reconciler.reconcile(
            session,
            1,
            seen_urls=set(),  # never seen in this run
            is_complete=True,
            is_authoritative=True,
        )
        assert result["closed"] == 1
        assert job_stale.status == JobStatus.closed.value

    async def test_get_stale_job_count(self) -> None:
        jobs = [
            _FakeJob("a", missing_count=MISSING_THRESHOLD),
            _FakeJob("b", missing_count=MISSING_THRESHOLD - 1),
            _FakeJob("c", missing_count=0),
        ]
        session = MagicMock()
        session.execute = AsyncMock(return_value=_FakeResult(jobs))
        reconciler = StaleReconciler()
        count = await reconciler.get_stale_job_count(session, 1)
        assert count == 1
