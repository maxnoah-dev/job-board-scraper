"""Unit tests for ``monitoring/metrics.py``."""

from __future__ import annotations

import pytest

from job_board_scraper.monitoring.metrics import (
    MetricsCollector,
    MetricType,
    ScrapeMetrics,
    get_metrics_collector,
)


class TestScrapeMetrics:
    def test_add_adapter_result_success(self) -> None:
        m = ScrapeMetrics(run_id="r1")
        m.add_adapter_result(succeeded=True, jobs_found=5, retries=1)
        assert m.total_adapters == 1
        assert m.succeeded_adapters == 1
        assert m.jobs_found == 5
        assert m.retry_count == 1

    def test_add_adapter_result_failure(self) -> None:
        m = ScrapeMetrics(run_id="r1")
        m.add_adapter_result(succeeded=False, jobs_found=0)
        assert m.failed_adapters == 1
        assert m.succeeded_adapters == 0

    def test_finalize(self) -> None:
        m = ScrapeMetrics(run_id="r1")
        m.finalize()
        assert m.ended_at is not None
        assert m.duration_ms >= 0

    def test_success_rate_zero_adapters(self) -> None:
        m = ScrapeMetrics(run_id="r1")
        assert m.success_rate == 0.0

    def test_success_rate(self) -> None:
        m = ScrapeMetrics(run_id="r1")
        m.add_adapter_result(succeeded=True)
        m.add_adapter_result(succeeded=True)
        m.add_adapter_result(succeeded=False)
        assert m.success_rate == pytest.approx(200 / 3)

    def test_to_dict(self) -> None:
        m = ScrapeMetrics(run_id="r1")
        data = m.to_dict()
        assert data["run_id"] == "r1"
        assert data["success_rate"] == 0.0
        assert data["errors"] == []


class TestMetricsCollector:
    def test_start_run(self) -> None:
        c = MetricsCollector()
        m = c.start_run("r1")
        assert isinstance(m, ScrapeMetrics)
        assert m.run_id == "r1"

    def test_get_run_by_id(self) -> None:
        c = MetricsCollector()
        c.start_run("r1")
        c.start_run("r2")
        assert c.get_run("r1").run_id == "r1"
        assert c.get_run("r2").run_id == "r2"
        assert c.get_run("missing") is None

    def test_get_latest(self) -> None:
        c = MetricsCollector()
        c.start_run("r1")
        c.start_run("r2")
        assert c.get_latest().run_id == "r2"

    def test_get_latest_empty(self) -> None:
        c = MetricsCollector()
        assert c.get_latest() is None

    def test_get_summary_empty(self) -> None:
        c = MetricsCollector()
        assert c.get_summary() == {
            "total_runs": 0,
            "total_jobs_found": 0,
            "avg_duration_ms": 0,
            "avg_success_rate": 0,
        }

    def test_get_summary_with_runs(self) -> None:
        c = MetricsCollector()
        m1 = c.start_run("r1")
        m1.add_adapter_result(succeeded=True, jobs_found=10)
        m1.finalize()
        m2 = c.start_run("r2")
        m2.add_adapter_result(succeeded=True, jobs_found=20)
        m2.finalize()
        summary = c.get_summary()
        assert summary["total_runs"] == 2
        assert summary["total_jobs_found"] == 30


def test_metric_type_values() -> None:
    assert MetricType.DURATION_MS.value == "duration_ms"
    assert MetricType.JOBS_FOUND.value == "jobs_found"


def test_get_metrics_collector_singleton() -> None:
    a = get_metrics_collector()
    b = get_metrics_collector()
    assert a is b
