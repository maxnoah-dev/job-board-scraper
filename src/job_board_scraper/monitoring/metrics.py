"""Metrics collector for scrape runs.

Collects and aggregates metrics from scrape runs for monitoring and reporting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class MetricType(Enum):
    """Types of metrics collected."""

    DURATION_MS = "duration_ms"
    JOBS_FOUND = "jobs_found"
    NEW_JOBS = "new_jobs"
    CLOSED_JOBS = "closed_jobs"
    FAILED_ADAPTERS = "failed_adapters"
    RETRY_COUNT = "retry_count"
    HTTP_REQUESTS = "http_requests"
    HTTP_ERRORS = "http_errors"
    RATE_LIMIT_HITS = "rate_limit_hits"


@dataclass
class ScrapeMetrics:
    """Metrics for a single scrape run."""

    run_id: str
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    ended_at: datetime | None = None
    duration_ms: int = 0
    jobs_found: int = 0
    new_jobs: int = 0
    closed_jobs: int = 0
    failed_adapters: int = 0
    succeeded_adapters: int = 0
    total_adapters: int = 0
    retry_count: int = 0
    http_requests: int = 0
    http_errors: int = 0
    rate_limit_hits: int = 0
    errors: list[str] = field(default_factory=list)

    def add_adapter_result(
        self,
        succeeded: bool,
        jobs_found: int = 0,
        retries: int = 0,
    ) -> None:
        """Record result from a single adapter."""
        self.total_adapters += 1
        if succeeded:
            self.succeeded_adapters += 1
            self.jobs_found += jobs_found
            self.new_jobs += jobs_found  # Simplified; real impl would diff
        else:
            self.failed_adapters += 1
        self.retry_count += retries

    def finalize(self) -> None:
        """Finalize metrics after run completes."""
        self.ended_at = datetime.now(UTC)
        self.duration_ms = int((self.ended_at - self.started_at).total_seconds() * 1000)

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_adapters == 0:
            return 0.0
        return (self.succeeded_adapters / self.total_adapters) * 100

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/export."""
        return {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_ms": self.duration_ms,
            "jobs_found": self.jobs_found,
            "new_jobs": self.new_jobs,
            "closed_jobs": self.closed_jobs,
            "failed_adapters": self.failed_adapters,
            "succeeded_adapters": self.succeeded_adapters,
            "total_adapters": self.total_adapters,
            "success_rate": round(self.success_rate, 2),
            "retry_count": self.retry_count,
            "http_requests": self.http_requests,
            "http_errors": self.http_errors,
            "rate_limit_hits": self.rate_limit_hits,
            "errors": self.errors,
        }


@dataclass
class MetricsCollector:
    """Collects metrics across multiple runs."""

    _runs: list[ScrapeMetrics] = field(default_factory=list)

    def start_run(self, run_id: str) -> ScrapeMetrics:
        """Start tracking a new scrape run."""
        metrics = ScrapeMetrics(run_id=run_id)
        self._runs.append(metrics)
        return metrics

    def get_run(self, run_id: str) -> ScrapeMetrics | None:
        """Get metrics for a specific run."""
        for run in reversed(self._runs):
            if run.run_id == run_id:
                return run
        return None

    def get_latest(self) -> ScrapeMetrics | None:
        """Get metrics for the most recent run."""
        return self._runs[-1] if self._runs else None

    def get_summary(self) -> dict:
        """Get summary statistics across all runs."""
        if not self._runs:
            return {
                "total_runs": 0,
                "total_jobs_found": 0,
                "avg_duration_ms": 0,
                "avg_success_rate": 0,
            }

        return {
            "total_runs": len(self._runs),
            "total_jobs_found": sum(r.jobs_found for r in self._runs),
            "avg_duration_ms": sum(r.duration_ms for r in self._runs)
            // len(self._runs),
            "avg_success_rate": sum(r.success_rate for r in self._runs)
            / len(self._runs),
        }


# Global metrics collector instance
_collector: MetricsCollector | None = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create the global metrics collector."""
    global _collector
    if _collector is None:
        _collector = MetricsCollector()
    return _collector
