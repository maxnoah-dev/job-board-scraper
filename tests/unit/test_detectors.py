"""Unit tests for ``monitoring/detectors.py``."""

from __future__ import annotations

from job_board_scraper.monitoring.detectors import (
    Anomaly,
    AnomalyType,
    JobCountHistory,
    TimeoutPatternDetector,
    ZeroJobDetector,
    get_timeout_detector,
    get_zero_job_detector,
)


class TestJobCountHistory:
    def test_average_empty(self) -> None:
        history = JobCountHistory(source="x")
        assert history.average == 0.0

    def test_average_with_counts(self) -> None:
        history = JobCountHistory(source="x")
        history.add_count(10)
        history.add_count(20)
        assert history.average == 15.0

    def test_window_size_trims(self) -> None:
        history = JobCountHistory(source="x", window_size=2)
        history.add_count(1)
        history.add_count(2)
        history.add_count(3)
        assert len(history.counts) == 2

    def test_last_count(self) -> None:
        history = JobCountHistory(source="x")
        assert history.last_count is None
        history.add_count(5)
        assert history.last_count == 5

    def test_trend_stable(self) -> None:
        history = JobCountHistory(source="x")
        history.add_count(5)
        history.add_count(5)
        assert history.trend == "stable"

    def test_trend_increasing(self) -> None:
        history = JobCountHistory(source="x")
        history.add_count(1)
        history.add_count(2)
        history.add_count(3)
        assert history.trend == "increasing"

    def test_trend_decreasing(self) -> None:
        history = JobCountHistory(source="x")
        history.add_count(3)
        history.add_count(2)
        history.add_count(1)
        assert history.trend == "decreasing"


class TestZeroJobDetector:
    def test_record_zero_with_history_returns_anomaly(self) -> None:
        detector = ZeroJobDetector()
        # Build a history of non-zero counts so the average is > 1.
        detector.record("opswat", 10)
        detector.record("opswat", 10)
        anomaly = detector.record("opswat", 0)
        assert isinstance(anomaly, Anomaly)
        assert anomaly.type == AnomalyType.ZERO_JOBS
        assert anomaly.severity == "error"

    def test_record_zero_without_history(self) -> None:
        detector = ZeroJobDetector()
        assert detector.record("new-source", 0) is None

    def test_record_decreasing_trend_returns_anomaly(self) -> None:
        detector = ZeroJobDetector()
        # Trend: decreasing across last 3 observations.
        detector.record("opswat", 100)
        detector.record("opswat", 50)
        detector.record("opswat", 25)
        anomaly = detector.record("opswat", 5)
        assert isinstance(anomaly, Anomaly)
        assert anomaly.type == AnomalyType.SUSPICIOUS_COUNT

    def test_record_normal_returns_none(self) -> None:
        detector = ZeroJobDetector()
        assert detector.record("opswat", 10) is None
        assert detector.record("opswat", 12) is None

    def test_get_history(self) -> None:
        detector = ZeroJobDetector()
        detector.record("opswat", 5)
        assert detector.get_history("opswat") is not None
        assert detector.get_history("missing") is None

    def test_get_all_histories(self) -> None:
        detector = ZeroJobDetector()
        detector.record("a", 5)
        detector.record("b", 10)
        assert set(detector.get_all_histories().keys()) == {"a", "b"}


class TestTimeoutPatternDetector:
    def test_record_timeout_below_threshold(self) -> None:
        detector = TimeoutPatternDetector(max_timeouts=3)
        assert detector.record_timeout("a") is None
        assert detector.record_timeout("a") is None

    def test_record_timeout_above_threshold(self) -> None:
        detector = TimeoutPatternDetector(max_timeouts=3)
        detector.record_timeout("a")
        detector.record_timeout("b")
        anomaly = detector.record_timeout("c")
        assert isinstance(anomaly, Anomaly)
        assert anomaly.type == AnomalyType.TIMEOUT_PATTERN
        assert anomaly.severity == "warning"


class TestAnomaly:
    def test_to_dict(self) -> None:
        a = Anomaly(
            type=AnomalyType.ZERO_JOBS,
            source="opswat",
            severity="error",
            title="Zero jobs",
            message="msg",
            metadata={"k": 1},
        )
        data = a.to_dict()
        assert data["type"] == "zero_jobs"
        assert data["source"] == "opswat"
        assert data["severity"] == "error"
        assert data["metadata"] == {"k": 1}


def test_get_zero_job_detector_singleton() -> None:
    a = get_zero_job_detector()
    b = get_zero_job_detector()
    assert a is b


def test_get_timeout_detector_singleton() -> None:
    a = get_timeout_detector()
    b = get_timeout_detector()
    assert a is b
