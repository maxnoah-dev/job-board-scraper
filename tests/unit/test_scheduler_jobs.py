"""Unit tests for ``scheduler/jobs.py``."""

from __future__ import annotations

import pytest

from job_board_scraper.scheduler.jobs import (
    JobScheduler,
    ScheduleType,
    ScrapeJob,
    get_scheduler,
)


class TestJobScheduler:
    def test_add_cron_job(self) -> None:
        sched = JobScheduler()
        job = sched.add_job(
            "daily", ScheduleType.CRON, companies=["opswat"], cron_expr="0 0 * * *"
        )
        assert isinstance(job, ScrapeJob)
        assert job.schedule_type == ScheduleType.CRON
        assert job.companies == ["opswat"]
        assert job.cron_expr == "0 0 * * *"

    def test_add_interval_job(self) -> None:
        sched = JobScheduler()
        job = sched.add_job(
            "every_hour", ScheduleType.INTERVAL, interval_seconds=3600
        )
        assert job.interval_seconds == 3600
        assert job.companies == []

    def test_remove_job(self) -> None:
        sched = JobScheduler()
        sched.add_job("a", ScheduleType.CRON)
        assert sched.remove_job("a") is True
        assert sched.remove_job("a") is False
        assert sched.remove_job("missing") is False

    def test_get_and_list(self) -> None:
        sched = JobScheduler()
        sched.add_job("a", ScheduleType.CRON)
        sched.add_job("b", ScheduleType.INTERVAL)
        assert sched.get_job("a").job_id == "a"
        assert sched.get_job("missing") is None
        assert len(sched.list_jobs()) == 2

    def test_enable_disable(self) -> None:
        sched = JobScheduler()
        sched.add_job("a", ScheduleType.CRON)
        assert sched.disable_job("a") is True
        assert sched.get_job("a").enabled is False
        assert sched.enable_job("a") is True
        assert sched.get_job("a").enabled is True
        assert sched.disable_job("missing") is False
        assert sched.enable_job("missing") is False

    @pytest.mark.asyncio
    async def test_run_job(self) -> None:
        sched = JobScheduler()
        sched.add_job("a", ScheduleType.CRON)
        assert await sched.run_job("a") is True
        assert await sched.run_job("missing") is False
        assert sched.get_job("a").last_run is not None


def test_get_scheduler_singleton() -> None:
    a = get_scheduler()
    b = get_scheduler()
    assert a is b


def test_schedule_type_values() -> None:
    assert ScheduleType.CRON.value == "cron"
    assert ScheduleType.INTERVAL.value == "interval"
    assert ScheduleType.ONE_SHOT.value == "one_shot"
