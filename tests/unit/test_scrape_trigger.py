"""Unit tests for ``web/services/scrape_trigger.py``."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from job_board_scraper.web.services.scrape_trigger import (
    RunSnapshot,
    ScrapeTrigger,
    ScrapeTriggerError,
)


@pytest.mark.asyncio
class TestScrapeTrigger:
    async def test_status_idle_when_no_runs(self) -> None:
        trigger = ScrapeTrigger()
        snap = await trigger.status()
        assert snap.state == "idle"
        assert snap.run_id is None

    async def test_status_returns_last_when_no_current(self) -> None:
        trigger = ScrapeTrigger()
        last = RunSnapshot(state="running", run_id=42, last_status="SUCCESS")
        trigger._last = last  # type: ignore[attr-defined]
        snap = await trigger.status()
        assert snap.run_id == 42

    async def test_resolve_factory_uses_default(self) -> None:
        trigger = ScrapeTrigger()
        factory = trigger._resolve_factory()
        assert callable(factory)

    async def test_resolve_factory_uses_explicit(self) -> None:
        custom = MagicMock()
        trigger = ScrapeTrigger(pipeline_factory=custom)
        assert trigger._resolve_factory() is custom

    async def test_start_raises_when_already_running(self) -> None:
        trigger = ScrapeTrigger()
        # Pre-populate a current run that is not yet done.
        ctx = MagicMock()
        ctx.done = asyncio.Event()
        trigger._current = ctx  # type: ignore[attr-defined]
        with pytest.raises(ScrapeTriggerError):
            await trigger.start(triggered_by="ui")

    async def test_start_creates_run_and_snapshot(self) -> None:
        from job_board_scraper.etl.pipeline import PipelineExitCode

        trigger = ScrapeTrigger()
        # Mock _create_run_row to avoid DB
        trigger._create_run_row = AsyncMock(return_value=99)  # type: ignore[method-assign]

        pipe = MagicMock()
        pipe.run = AsyncMock(
            return_value=MagicMock(status=PipelineExitCode.SUCCESS)
        )

        trigger._pipeline_factory = lambda: pipe
        snap = await trigger.start(triggered_by="ui", dry_run=True)
        assert snap.state == "running"
        assert snap.run_id == 99
        # Wait for the background task to finish so the test can exit cleanly.
        if trigger._task:
            await trigger._task
        assert trigger._last.last_status == "success"  # type: ignore[union-attr]

    async def test_pipeline_error_marks_failed(self) -> None:
        trigger = ScrapeTrigger()
        trigger._create_run_row = AsyncMock(return_value=1)  # type: ignore[method-assign]

        pipe = MagicMock()
        pipe.run = AsyncMock(side_effect=RuntimeError("boom"))

        trigger._pipeline_factory = lambda: pipe
        await trigger.start()
        if trigger._task:
            await trigger._task
        assert trigger._last.last_status == "failed"  # type: ignore[union-attr]
        assert "boom" in trigger._last.last_error  # type: ignore[union-attr]


class TestRunSnapshot:
    def test_to_dict(self) -> None:
        snap = RunSnapshot(
            state="running",
            run_id=1,
            triggered_by="ui",
            company_slug="opswat",
            started_at=datetime(2026, 1, 1, tzinfo=UTC),
            finished_at=datetime(2026, 1, 1, 0, 0, 5, tzinfo=UTC),
            last_status="SUCCESS",
        )
        data = snap.to_dict()
        assert data["state"] == "running"
        assert data["run_id"] == 1
        assert data["started_at"].startswith("2026-01-01")
        assert data["finished_at"].startswith("2026-01-01")

    def test_to_dict_with_none_dates(self) -> None:
        snap = RunSnapshot(state="idle")
        data = snap.to_dict()
        assert data["started_at"] is None
        assert data["finished_at"] is None


class TestScrapeTriggerError:
    def test_default_status_code(self) -> None:
        err = ScrapeTriggerError("oops")
        assert err.status_code == 409

    def test_custom_status_code(self) -> None:
        err = ScrapeTriggerError("oops", status_code=503)
        assert err.status_code == 503
