"""Zero-job and anomaly detectors for monitoring.

Detects anomalies like zero jobs, suspicious activity, and selector drift.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class AnomalyType(Enum):
    """Types of anomalies detected."""

    ZERO_JOBS = "zero_jobs"
    SUSPICIOUS_COUNT = "suspicious_count"
    SELECTOR_DRIFT = "selector_drift"
    TIMEOUT_PATTERN = "timeout_pattern"
    HIGH_ERROR_RATE = "high_error_rate"


@dataclass
class Anomaly:
    """An detected anomaly."""

    type: AnomalyType
    source: str
    severity: str  # debug, info, warning, error, critical
    title: str
    message: str
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "type": self.type.value,
            "source": self.source,
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "detected_at": self.detected_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class JobCountHistory:
    """Historical job count data for a source."""

    source: str
    counts: list[tuple[datetime, int]] = field(default_factory=list)
    window_size: int = 10  # Number of historical runs to keep

    def add_count(self, count: int) -> None:
        """Add a job count observation."""
        self.counts.append((datetime.now(UTC), count))
        if len(self.counts) > self.window_size:
            self.counts.pop(0)

    @property
    def average(self) -> float:
        """Calculate average job count."""
        if not self.counts:
            return 0.0
        return sum(c for _, c in self.counts) / len(self.counts)

    @property
    def last_count(self) -> int | None:
        """Get the most recent job count."""
        if not self.counts:
            return None
        return self.counts[-1][1]

    @property
    def trend(self) -> str:
        """Get trend direction: 'increasing', 'decreasing', or 'stable'."""
        if len(self.counts) < 3:
            return "stable"

        recent = [c for _, c in self.counts[-3:]]
        oldest, middle, newest = recent

        if newest > middle > oldest:
            return "increasing"
        elif newest < middle < oldest:
            return "decreasing"
        return "stable"


class ZeroJobDetector:
    """Detects zero-job anomalies."""

    def __init__(
        self,
        history_window: int = 5,
        min_expected_jobs: int = 1,
    ) -> None:
        self._history: dict[str, JobCountHistory] = {}
        self._history_window = history_window
        self._min_expected_jobs = min_expected_jobs

    def record(self, source: str, job_count: int) -> Anomaly | None:
        """Record a job count and detect anomalies.

        Returns an Anomaly if one is detected, None otherwise.
        """
        if source not in self._history:
            self._history[source] = JobCountHistory(source=source)

        history = self._history[source]
        history.add_count(job_count)

        # Detect zero jobs when we expected some
        if job_count == 0 and history.average > self._min_expected_jobs:
            return Anomaly(
                type=AnomalyType.ZERO_JOBS,
                source=source,
                severity="error",
                title=f"Zero jobs from {source}",
                message=(
                    f"Source {source} returned 0 jobs. "
                    f"Average over last {len(history.counts)} runs: {history.average:.1f}. "
                    f"Possible selector drift or anti-bot blocking."
                ),
                metadata={
                    "current_count": job_count,
                    "average_count": history.average,
                    "history": [(ts.isoformat(), c) for ts, c in history.counts],
                    "trend": history.trend,
                },
            )

        # Detect suspicious patterns
        if history.last_count is not None:
            if (
                history.trend == "decreasing"
                and history.last_count < history.average * 0.5
            ):
                return Anomaly(
                    type=AnomalyType.SUSPICIOUS_COUNT,
                    source=source,
                    severity="warning",
                    title=f"Suspicious job count drop for {source}",
                    message=(
                        f"Job count dropped significantly for {source}. "
                        f"Current: {history.last_count}, Average: {history.average:.1f}"
                    ),
                    metadata={
                        "current_count": history.last_count,
                        "average_count": history.average,
                        "trend": history.trend,
                    },
                )

        return None

    def get_history(self, source: str) -> JobCountHistory | None:
        """Get job count history for a source."""
        return self._history.get(source)

    def get_all_histories(self) -> dict[str, JobCountHistory]:
        """Get all job count histories."""
        return self._history.copy()


class TimeoutPatternDetector:
    """Detects timeout patterns that might indicate infrastructure issues."""

    def __init__(
        self,
        window_seconds: int = 300,
        max_timeouts: int = 3,
    ) -> None:
        self._window = timedelta(seconds=window_seconds)
        self._max_timeouts = max_timeouts
        self._timeouts: list[tuple[datetime, str]] = []

    def record_timeout(self, source: str) -> Anomaly | None:
        """Record a timeout and check for pattern.

        Returns an Anomaly if threshold exceeded, None otherwise.
        """
        now = datetime.now(UTC)
        self._timeouts.append((now, source))

        # Clean up old timeouts
        cutoff = now - self._window
        self._timeouts = [(ts, s) for ts, s in self._timeouts if ts > cutoff]

        # Check threshold
        if len(self._timeouts) >= self._max_timeouts:
            sources = set(s for _, s in self._timeouts)
            return Anomaly(
                type=AnomalyType.TIMEOUT_PATTERN,
                source=", ".join(sorted(sources)),
                severity="warning",
                title="Multiple timeouts detected",
                message=(
                    f"{len(self._timeouts)} timeouts in the last {self._window.total_seconds():.0f}s "
                    f"from {len(sources)} source(s): {', '.join(sorted(sources))}"
                ),
                metadata={
                    "timeout_count": len(self._timeouts),
                    "sources": list(sources),
                    "window_seconds": self._window.total_seconds(),
                },
            )

        return None


# Global detector instances
_zero_job_detector: ZeroJobDetector | None = None
_timeout_detector: TimeoutPatternDetector | None = None


def get_zero_job_detector() -> ZeroJobDetector:
    """Get or create the global zero-job detector."""
    global _zero_job_detector
    if _zero_job_detector is None:
        _zero_job_detector = ZeroJobDetector()
    return _zero_job_detector


def get_timeout_detector() -> TimeoutPatternDetector:
    """Get or create the global timeout detector."""
    global _timeout_detector
    if _timeout_detector is None:
        _timeout_detector = TimeoutPatternDetector()
    return _timeout_detector
