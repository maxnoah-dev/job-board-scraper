"""Multi-adapter orchestration.

Provides concurrent execution of multiple adapters with:
- Semaphore-based concurrency limiting (max 5 concurrent)
- Partial failure handling
- Aggregated metrics collection
- Per-adapter status tracking
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from job_board_scraper.adapters.base import BaseAdapter

if TYPE_CHECKING:
    from job_board_scraper.models.job import RawJobData


logger = logging.getLogger(__name__)


class AdapterRunStatus(Enum):
    """Status of an individual adapter run."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class AdapterMetrics:
    """Metrics collected from a single adapter run."""

    slug: str
    status: AdapterRunStatus = AdapterRunStatus.PENDING
    jobs_found: int = 0
    pages_fetched: int = 0
    requests_made: int = 0
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @property
    def duration_ms(self) -> int | None:
        """Calculate duration in milliseconds."""
        if self.started_at and self.finished_at:
            delta = self.finished_at - self.started_at
            return int(delta.total_seconds() * 1000)
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "slug": self.slug,
            "status": self.status.value,
            "jobs_found": self.jobs_found,
            "pages_fetched": self.pages_fetched,
            "requests_made": self.requests_made,
            "warnings": self.warnings,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_ms": self.duration_ms,
        }


@dataclass
class AggregatedMetrics:
    """Aggregated metrics across all adapter runs."""

    total_adapters: int = 0
    successful: int = 0
    partial: int = 0
    failed: int = 0
    skipped: int = 0
    total_jobs_found: int = 0
    total_pages_fetched: int = 0
    total_requests_made: int = 0
    total_warnings: int = 0
    total_duration_ms: int = 0

    @classmethod
    def from_adapter_metrics(cls, metrics: list[AdapterMetrics]) -> AggregatedMetrics:
        """Create aggregated metrics from individual adapter metrics."""
        agg = cls()
        agg.total_adapters = len(metrics)

        for m in metrics:
            if m.status == AdapterRunStatus.SUCCESS:
                agg.successful += 1
            elif m.status == AdapterRunStatus.PARTIAL:
                agg.partial += 1
            elif m.status == AdapterRunStatus.FAILED:
                agg.failed += 1
            elif m.status == AdapterRunStatus.SKIPPED:
                agg.skipped += 1

            agg.total_jobs_found += m.jobs_found
            agg.total_pages_fetched += m.pages_fetched
            agg.total_requests_made += m.requests_made
            agg.total_warnings += len(m.warnings)

            if m.duration_ms:
                agg.total_duration_ms += m.duration_ms

        return agg

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_adapters": self.total_adapters,
            "successful": self.successful,
            "partial": self.partial,
            "failed": self.failed,
            "skipped": self.skipped,
            "total_jobs_found": self.total_jobs_found,
            "total_pages_fetched": self.total_pages_fetched,
            "total_requests_made": self.total_requests_made,
            "total_warnings": self.total_warnings,
            "total_duration_ms": self.total_duration_ms,
        }


@dataclass
class MultiAdapterResult:
    """Result of running multiple adapters."""

    adapter_metrics: list[AdapterMetrics]
    aggregated: AggregatedMetrics
    all_jobs: list[RawJobData] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "adapter_metrics": [m.to_dict() for m in self.adapter_metrics],
            "aggregated": self.aggregated.to_dict(),
            "all_jobs_count": len(self.all_jobs),
        }


class MultiAdapterOrchestrator:
    """Orchestrates concurrent execution of multiple adapters.

    Features:
    - Semaphore-based concurrency limiting (configurable, default 5)
    - Partial failure handling (adapters can fail independently)
    - Per-adapter metrics collection
    - Aggregated metrics reporting
    - Graceful handling of adapter exceptions
    """

    def __init__(self, max_concurrent: int = 5) -> None:
        """Initialize orchestrator.

        Args:
            max_concurrent: Maximum number of adapters to run concurrently.
        """
        self._max_concurrent = max_concurrent
        self._semaphore: asyncio.Semaphore | None = None

    async def run_adapters(
        self,
        adapters: dict[str, BaseAdapter],
    ) -> MultiAdapterResult:
        """Run multiple adapters concurrently with semaphore limiting.

        Args:
            adapters: Dict mapping adapter slug to adapter instance.

        Returns:
            MultiAdapterResult with per-adapter metrics and aggregated stats.
        """
        if not adapters:
            return MultiAdapterResult(
                adapter_metrics=[],
                aggregated=AggregatedMetrics(),
                all_jobs=[],
            )

        # Initialize semaphore if needed
        self._semaphore = asyncio.Semaphore(self._max_concurrent)

        # Initialize metrics for each adapter
        metrics_by_slug: dict[str, AdapterMetrics] = {
            slug: AdapterMetrics(slug=slug) for slug in adapters
        }

        async def run_single(slug: str, adapter: BaseAdapter) -> AdapterMetrics:
            """Run a single adapter with semaphore protection."""
            async with self._semaphore:
                metrics = metrics_by_slug[slug]
                metrics.status = AdapterRunStatus.RUNNING
                metrics.started_at = datetime.now(UTC)

                try:
                    result = await adapter.fetch_jobs()
                    metrics.jobs_found = len(result.jobs)
                    metrics.pages_fetched = result.pages_fetched
                    metrics.requests_made = result.requests_made
                    metrics.warnings = result.warnings

                    if result.status.value == "success":
                        metrics.status = AdapterRunStatus.SUCCESS
                    elif result.status.value == "partial":
                        metrics.status = AdapterRunStatus.PARTIAL
                    else:
                        metrics.status = AdapterRunStatus.FAILED
                        metrics.error = result.error

                except Exception as e:
                    logger.exception(f"Adapter {slug} failed with exception")
                    metrics.status = AdapterRunStatus.FAILED
                    metrics.error = f"{type(e).__name__}: {str(e)}"

                finally:
                    metrics.finished_at = datetime.now(UTC)

                return metrics

        # Run all adapters concurrently
        tasks = [run_single(slug, adapter) for slug, adapter in adapters.items()]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        adapter_metrics: list[AdapterMetrics] = []
        all_jobs: list[RawJobData] = []

        for result in results:
            if isinstance(result, AdapterMetrics):
                adapter_metrics.append(result)
            elif isinstance(result, Exception):
                # This shouldn't happen since we catch in run_single, but just in case
                logger.exception("Unexpected exception in gather")

        # Calculate aggregated metrics
        aggregated = AggregatedMetrics.from_adapter_metrics(adapter_metrics)

        return MultiAdapterResult(
            adapter_metrics=adapter_metrics,
            aggregated=aggregated,
            all_jobs=all_jobs,
        )

    async def run_with_fallback(
        self,
        adapters: dict[str, BaseAdapter],
        fallback_adapter: BaseAdapter | None = None,
    ) -> MultiAdapterResult:
        """Run adapters with a fallback adapter if all primary adapters fail.

        Args:
            adapters: Primary adapters to run.
            fallback_adapter: Fallback adapter if all primaries fail.

        Returns:
            MultiAdapterResult with results from all attempted adapters.
        """
        result = await self.run_adapters(adapters)

        # Check if we need to run fallback
        if (
            fallback_adapter
            and result.aggregated.failed == result.aggregated.total_adapters
        ):
            logger.info(
                f"All {result.aggregated.total_adapters} primary adapters failed, "
                f"running fallback adapter: {fallback_adapter.slug}"
            )

            fallback_result = await self.run_adapters(
                {fallback_adapter.slug: fallback_adapter}
            )

            # Merge results
            result.adapter_metrics.extend(fallback_result.adapter_metrics)
            result.aggregated = AggregatedMetrics.from_adapter_metrics(
                result.adapter_metrics
            )

        return result


class AdapterSelector:
    """Selects adapters based on various criteria."""

    @staticmethod
    def by_type(
        adapters: dict[str, BaseAdapter], adapter_type: str
    ) -> dict[str, BaseAdapter]:
        """Select adapters by type (api, html, browser).

        Args:
            adapters: All available adapters.
            adapter_type: Type to filter by.

        Returns:
            Dict of adapters matching the type.
        """
        return {
            slug: adapter
            for slug, adapter in adapters.items()
            if adapter.adapter_type == adapter_type
        }

    @staticmethod
    def by_slug(
        adapters: dict[str, BaseAdapter], slugs: list[str]
    ) -> dict[str, BaseAdapter]:
        """Select adapters by slug.

        Args:
            adapters: All available adapters.
            slugs: List of slugs to include.

        Returns:
            Dict of adapters matching the slugs.
        """
        return {slug: adapters[slug] for slug in slugs if slug in adapters}

    @staticmethod
    def exclude(
        adapters: dict[str, BaseAdapter], exclude_slugs: list[str]
    ) -> dict[str, BaseAdapter]:
        """Exclude adapters by slug.

        Args:
            adapters: All available adapters.
            exclude_slugs: List of slugs to exclude.

        Returns:
            Dict of adapters excluding the specified slugs.
        """
        return {
            slug: adapter
            for slug, adapter in adapters.items()
            if slug not in exclude_slugs
        }
