"""Unit tests for the multi-adapter orchestration module (etl/multi_adapter.py).

Covers:
- MultiAdapterOrchestrator initialization
- Concurrent adapter execution with semaphore
- Partial failure handling
- Aggregated metrics collection
- AdapterSelector filtering
"""

from __future__ import annotations

from datetime import UTC

import pytest

from job_board_scraper.adapters.base import (
    ExtractionResult,
    ExtractionStatus,
)
from job_board_scraper.etl.multi_adapter import (
    AdapterMetrics,
    AdapterRunStatus,
    AdapterSelector,
    AggregatedMetrics,
    MultiAdapterOrchestrator,
    MultiAdapterResult,
)


class DummyAdapter:
    """Minimal BaseAdapter implementation for testing."""

    def __init__(
        self,
        slug: str,
        adapter_type: str = "api",
        base_url: str = "https://example.com",
        jobs_to_return: int = 5,
        should_fail: bool = False,
        delay: float = 0.01,
    ) -> None:
        self.slug = slug
        self.adapter_type = adapter_type
        self.base_url = base_url
        self.jobs_to_return = jobs_to_return
        self.should_fail = should_fail
        self.delay = delay

    async def fetch_jobs(self) -> ExtractionResult:
        import asyncio

        if self.delay > 0:
            await asyncio.sleep(self.delay)

        if self.should_fail:
            raise RuntimeError(f"Adapter {self.slug} intentionally failed")

        return ExtractionResult(
            jobs=[
                {
                    "source_company_id": self.slug,
                    "title": f"Job {i}",
                    "url": f"https://example.com/{self.slug}/{i}",
                }
                for i in range(self.jobs_to_return)
            ],
            status=ExtractionStatus.SUCCESS,
            pages_fetched=1,
            requests_made=1,
        )

    async def close(self) -> None:
        pass


class TestAdapterMetrics:
    """AdapterMetrics tracks individual adapter performance."""

    def test_initialization(self) -> None:
        metrics = AdapterMetrics(slug="test-adapter")
        assert metrics.slug == "test-adapter"
        assert metrics.status == AdapterRunStatus.PENDING
        assert metrics.jobs_found == 0
        assert metrics.pages_fetched == 0
        assert metrics.requests_made == 0
        assert metrics.warnings == []
        assert metrics.error is None

    def test_duration_ms_calculated(self) -> None:

        metrics = AdapterMetrics(slug="test")
        from datetime import datetime

        metrics.started_at = datetime(2026, 7, 24, 10, 0, 0, tzinfo=UTC)
        metrics.finished_at = datetime(2026, 7, 24, 10, 0, 1, 500000, tzinfo=UTC)

        assert metrics.duration_ms == 1500

    def test_duration_ms_none_if_not_finished(self) -> None:
        metrics = AdapterMetrics(slug="test")
        assert metrics.duration_ms is None

    def test_to_dict_serialization(self) -> None:
        from datetime import datetime

        metrics = AdapterMetrics(
            slug="test",
            status=AdapterRunStatus.SUCCESS,
            jobs_found=10,
            pages_fetched=2,
            requests_made=3,
            warnings=["Warning 1"],
        )
        metrics.started_at = datetime(2026, 7, 24, 10, 0, 0, tzinfo=UTC)
        metrics.finished_at = datetime(2026, 7, 24, 10, 0, 1, tzinfo=UTC)

        data = metrics.to_dict()

        assert data["slug"] == "test"
        assert data["status"] == "success"
        assert data["jobs_found"] == 10
        assert data["pages_fetched"] == 2
        assert data["requests_made"] == 3
        assert data["warnings"] == ["Warning 1"]
        assert data["duration_ms"] == 1000


class TestAggregatedMetrics:
    """AggregatedMetrics combines metrics from multiple adapters."""

    def test_empty_metrics(self) -> None:
        agg = AggregatedMetrics()
        assert agg.total_adapters == 0
        assert agg.successful == 0

    def test_from_adapter_metrics_success(self) -> None:
        from datetime import datetime

        metrics = [
            AdapterMetrics(
                slug="adapter1",
                status=AdapterRunStatus.SUCCESS,
                jobs_found=10,
                pages_fetched=2,
                requests_made=3,
            ),
            AdapterMetrics(
                slug="adapter2",
                status=AdapterRunStatus.SUCCESS,
                jobs_found=5,
                pages_fetched=1,
                requests_made=1,
            ),
        ]
        metrics[0].started_at = datetime.now(UTC)
        metrics[0].finished_at = datetime.now(UTC)

        agg = AggregatedMetrics.from_adapter_metrics(metrics)

        assert agg.total_adapters == 2
        assert agg.successful == 2
        assert agg.total_jobs_found == 15
        assert agg.total_pages_fetched == 3
        assert agg.total_requests_made == 4

    def test_from_adapter_metrics_mixed_status(self) -> None:
        metrics = [
            AdapterMetrics(slug="s1", status=AdapterRunStatus.SUCCESS, jobs_found=10),
            AdapterMetrics(
                slug="s2",
                status=AdapterRunStatus.PARTIAL,
                jobs_found=5,
                warnings=["Warn"],
            ),
            AdapterMetrics(slug="s3", status=AdapterRunStatus.FAILED, error="Error"),
            AdapterMetrics(slug="s4", status=AdapterRunStatus.SKIPPED),
        ]

        agg = AggregatedMetrics.from_adapter_metrics(metrics)

        assert agg.total_adapters == 4
        assert agg.successful == 1
        assert agg.partial == 1
        assert agg.failed == 1
        assert agg.skipped == 1
        assert agg.total_jobs_found == 15
        assert agg.total_warnings == 1


class TestMultiAdapterOrchestrator:
    """MultiAdapterOrchestrator runs adapters concurrently with limits."""

    @pytest.mark.asyncio
    async def test_empty_adapters_returns_empty_result(self) -> None:
        orchestrator = MultiAdapterOrchestrator()
        result = await orchestrator.run_adapters({})

        assert len(result.adapter_metrics) == 0
        assert result.aggregated.total_adapters == 0

    @pytest.mark.asyncio
    async def test_single_adapter_success(self) -> None:
        adapter = DummyAdapter("test-adapter", jobs_to_return=5)
        orchestrator = MultiAdapterOrchestrator()

        result = await orchestrator.run_adapters({"test-adapter": adapter})

        assert len(result.adapter_metrics) == 1
        assert result.aggregated.total_adapters == 1
        assert result.aggregated.successful == 1
        assert result.aggregated.total_jobs_found == 5

    @pytest.mark.asyncio
    async def test_multiple_adapters_concurrent(self) -> None:
        adapters = {
            f"adapter-{i}": DummyAdapter(f"adapter-{i}", delay=0.05) for i in range(3)
        }
        orchestrator = MultiAdapterOrchestrator(max_concurrent=5)

        result = await orchestrator.run_adapters(adapters)

        assert result.aggregated.total_adapters == 3
        assert result.aggregated.successful == 3
        assert result.aggregated.total_jobs_found == 15

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self) -> None:
        import asyncio

        concurrent_count = 0
        max_concurrent = 0
        lock = asyncio.Lock()

        class CountingAdapter(DummyAdapter):
            async def fetch_jobs(self) -> ExtractionResult:
                nonlocal concurrent_count, max_concurrent

                async with lock:
                    concurrent_count += 1
                    max_concurrent = max(max_concurrent, concurrent_count)

                await asyncio.sleep(0.1)

                async with lock:
                    concurrent_count -= 1

                return await super().fetch_jobs()

        adapters = {f"adapter-{i}": CountingAdapter(f"adapter-{i}") for i in range(5)}
        orchestrator = MultiAdapterOrchestrator(max_concurrent=3)

        await orchestrator.run_adapters(adapters)

        assert max_concurrent <= 3

    @pytest.mark.asyncio
    async def test_partial_failure_handling(self) -> None:
        adapters = {
            "success-1": DummyAdapter("success-1", jobs_to_return=5),
            "fail-1": DummyAdapter("fail-1", should_fail=True),
            "success-2": DummyAdapter("success-2", jobs_to_return=3),
        }
        orchestrator = MultiAdapterOrchestrator()

        result = await orchestrator.run_adapters(adapters)

        assert result.aggregated.total_adapters == 3
        assert result.aggregated.successful == 2
        assert result.aggregated.failed == 1
        assert result.aggregated.total_jobs_found == 8

        # Check that the failed adapter has an error
        failed_metrics = next(m for m in result.adapter_metrics if m.slug == "fail-1")
        assert failed_metrics.status == AdapterRunStatus.FAILED
        assert failed_metrics.error is not None

    @pytest.mark.asyncio
    async def test_all_failures_return_failed_status(self) -> None:
        adapters = {
            "fail-1": DummyAdapter("fail-1", should_fail=True),
            "fail-2": DummyAdapter("fail-2", should_fail=True),
        }
        orchestrator = MultiAdapterOrchestrator()

        result = await orchestrator.run_adapters(adapters)

        assert result.aggregated.total_adapters == 2
        assert result.aggregated.failed == 2

    @pytest.mark.asyncio
    async def test_metrics_have_timing_info(self) -> None:
        adapter = DummyAdapter("test-adapter", delay=0.02)
        orchestrator = MultiAdapterOrchestrator()

        result = await orchestrator.run_adapters({"test-adapter": adapter})

        metrics = result.adapter_metrics[0]
        assert metrics.started_at is not None
        assert metrics.finished_at is not None
        assert metrics.duration_ms is not None
        assert metrics.duration_ms >= 20  # At least the delay

    @pytest.mark.asyncio
    async def test_warnings_collected(self) -> None:
        class WarningAdapter(DummyAdapter):
            async def fetch_jobs(self) -> ExtractionResult:
                return ExtractionResult(
                    jobs=[{"title": "Job", "url": "https://example.com/1"}],
                    status=ExtractionStatus.SUCCESS,
                    warnings=["Warning 1", "Warning 2"],
                    pages_fetched=1,
                    requests_made=1,
                )

        orchestrator = MultiAdapterOrchestrator()
        result = await orchestrator.run_adapters(
            {"warning-adapter": WarningAdapter("warning-adapter")}
        )

        assert result.adapter_metrics[0].warnings == ["Warning 1", "Warning 2"]


class TestMultiAdapterResult:
    """MultiAdapterResult aggregates all adapter results."""

    def test_to_dict_serialization(self) -> None:
        metrics = [
            AdapterMetrics(
                slug="test-1",
                status=AdapterRunStatus.SUCCESS,
                jobs_found=10,
            ),
        ]
        aggregated = AggregatedMetrics.from_adapter_metrics(metrics)

        result = MultiAdapterResult(
            adapter_metrics=metrics,
            aggregated=aggregated,
        )

        data = result.to_dict()

        assert "adapter_metrics" in data
        assert "aggregated" in data
        assert len(data["adapter_metrics"]) == 1
        assert data["aggregated"]["total_adapters"] == 1


class TestAdapterSelector:
    """AdapterSelector filters adapters by various criteria."""

    def test_by_type_filters_correctly(self) -> None:
        adapters = {
            "api-1": DummyAdapter("api-1", adapter_type="api"),
            "html-1": DummyAdapter("html-1", adapter_type="html"),
            "browser-1": DummyAdapter("browser-1", adapter_type="browser"),
            "api-2": DummyAdapter("api-2", adapter_type="api"),
        }

        api_adapters = AdapterSelector.by_type(adapters, "api")
        assert len(api_adapters) == 2
        assert "api-1" in api_adapters
        assert "api-2" in api_adapters
        assert "html-1" not in api_adapters

    def test_by_slug_filters_correctly(self) -> None:
        adapters = {
            "adapter-1": DummyAdapter("adapter-1"),
            "adapter-2": DummyAdapter("adapter-2"),
            "adapter-3": DummyAdapter("adapter-3"),
        }

        selected = AdapterSelector.by_slug(adapters, ["adapter-1", "adapter-3"])
        assert len(selected) == 2
        assert "adapter-1" in selected
        assert "adapter-3" in selected
        assert "adapter-2" not in selected

    def test_by_slug_ignores_missing(self) -> None:
        adapters = {
            "adapter-1": DummyAdapter("adapter-1"),
        }

        selected = AdapterSelector.by_slug(adapters, ["adapter-1", "nonexistent"])
        assert len(selected) == 1
        assert "adapter-1" in selected

    def test_exclude_removes_correctly(self) -> None:
        adapters = {
            "keep-1": DummyAdapter("keep-1"),
            "exclude-1": DummyAdapter("exclude-1"),
            "keep-2": DummyAdapter("keep-2"),
        }

        filtered = AdapterSelector.exclude(adapters, ["exclude-1"])
        assert len(filtered) == 2
        assert "keep-1" in filtered
        assert "keep-2" in filtered
        assert "exclude-1" not in filtered


class TestMultiAdapterOrchestratorEdgeCases:
    """Edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_adapter_with_zero_jobs(self) -> None:
        adapter = DummyAdapter("empty-adapter", jobs_to_return=0)
        orchestrator = MultiAdapterOrchestrator()

        result = await orchestrator.run_adapters({"empty-adapter": adapter})

        assert result.aggregated.successful == 1
        assert result.aggregated.total_jobs_found == 0

    @pytest.mark.asyncio
    async def test_exception_during_gather_is_handled(self) -> None:
        # Even if gather returns an exception (shouldn't happen), we handle it
        adapters = {
            "test": DummyAdapter("test"),
        }
        orchestrator = MultiAdapterOrchestrator()

        result = await orchestrator.run_adapters(adapters)

        # Should not crash and should have results
        assert result.aggregated.total_adapters >= 1
