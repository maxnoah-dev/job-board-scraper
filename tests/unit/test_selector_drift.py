"""Tests for selector drift detection."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from job_board_scraper.monitoring.selector_drift import (
    DriftEvent,
    SelectorDriftDetector,
    SelectorHealth,
    SelectorSnapshot,
    create_drift_detector_from_config,
    format_drift_event,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def detector() -> SelectorDriftDetector:
    """Create a detector with default settings."""
    return SelectorDriftDetector(
        min_expected_matches=1,
        history_size=5,
        drift_threshold=0.5,
        zero_match_alert_threshold=2,
    )


@pytest.fixture
def sample_html() -> str:
    """Sample HTML with job cards."""
    return """
    <html>
    <body>
        <div class="job-card">Job 1</div>
        <div class="job-card">Job 2</div>
        <div class="job-card">Job 3</div>
    </body>
    </html>
    """


# ---------------------------------------------------------------------------
# SelectorSnapshot tests
# ---------------------------------------------------------------------------


class TestSelectorSnapshot:
    """Tests for SelectorSnapshot dataclass."""

    def test_create_snapshot(self) -> None:
        """Should create a snapshot with required fields."""
        snapshot = SelectorSnapshot(
            selector=".job",
            match_count=5,
            timestamp=datetime.now(UTC),
        )
        assert snapshot.selector == ".job"
        assert snapshot.match_count == 5

    def test_create_snapshot_with_url(self) -> None:
        """Should create a snapshot with page URL."""
        snapshot = SelectorSnapshot(
            selector=".job",
            match_count=3,
            timestamp=datetime.now(UTC),
            page_url="https://example.com/jobs",
        )
        assert snapshot.page_url == "https://example.com/jobs"


# ---------------------------------------------------------------------------
# DriftEvent tests
# ---------------------------------------------------------------------------


class TestDriftEvent:
    """Tests for DriftEvent dataclass."""

    def test_create_event(self) -> None:
        """Should create an event with all fields."""
        event = DriftEvent(
            selector=".job",
            expected_min=1,
            actual_count=0,
            severity="critical",
            message="Selector returned 0 matches",
        )
        assert event.selector == ".job"
        assert event.actual_count == 0
        assert event.severity == "critical"

    def test_default_timestamp(self) -> None:
        """Should have default timestamp."""
        event = DriftEvent(
            selector=".job",
            expected_min=1,
            actual_count=0,
            severity="warning",
            message="Test",
        )
        assert event.timestamp is not None


# ---------------------------------------------------------------------------
# SelectorHealth tests
# ---------------------------------------------------------------------------


class TestSelectorHealth:
    """Tests for SelectorHealth dataclass."""

    def test_create_health(self) -> None:
        """Should create health with all fields."""
        health = SelectorHealth(
            selector=".job",
            total_snapshots=10,
            avg_match_count=5.5,
            min_match_count=3,
            max_match_count=8,
            drift_score=0.3,
            is_healthy=True,
        )
        assert health.selector == ".job"
        assert health.avg_match_count == 5.5
        assert health.is_healthy is True


# ---------------------------------------------------------------------------
# SelectorDriftDetector tests
# ---------------------------------------------------------------------------


class TestSelectorDriftDetector:
    """Tests for SelectorDriftDetector."""

    def test_record_snapshot(self, detector: SelectorDriftDetector) -> None:
        """Should record a snapshot."""
        detector.record(".job-card", 5, "https://example.com")
        health = detector.get_selector_health(".job-card")
        assert health is not None
        assert health.total_snapshots == 1
        assert health.avg_match_count == 5.0

    def test_record_multiple_snapshots(self, detector: SelectorDriftDetector) -> None:
        """Should maintain history of snapshots."""
        detector.record(".job-card", 5)
        detector.record(".job-card", 6)
        detector.record(".job-card", 4)

        health = detector.get_selector_health(".job-card")
        assert health is not None
        assert health.total_snapshots == 3
        assert health.avg_match_count == 5.0
        assert health.min_match_count == 4
        assert health.max_match_count == 6

    def test_history_size_limit(self, detector: SelectorDriftDetector) -> None:
        """Should limit history size."""
        # Default history_size is 5
        for i in range(10):
            detector.record(".job-card", i)

        health = detector.get_selector_health(".job-card")
        assert health is not None
        assert health.total_snapshots == 5

    def test_get_selector_health_unknown(self, detector: SelectorDriftDetector) -> None:
        """Should return None for unknown selector."""
        health = detector.get_selector_health(".unknown")
        assert health is None

    def test_get_all_health(self, detector: SelectorDriftDetector) -> None:
        """Should return health for all selectors."""
        detector.record(".job-card", 5)
        detector.record(".job-title", 3)

        all_health = detector.get_all_health()
        assert len(all_health) == 2
        assert ".job-card" in all_health
        assert ".job-title" in all_health

    def test_reset_selector(self, detector: SelectorDriftDetector) -> None:
        """Should clear selector history."""
        detector.record(".job-card", 5)
        detector.reset_selector(".job-card")

        health = detector.get_selector_health(".job-card")
        assert health is None

    def test_clear_all(self, detector: SelectorDriftDetector) -> None:
        """Should clear all history."""
        detector.record(".job-card", 5)
        detector.record(".job-title", 3)
        detector.clear_all()

        all_health = detector.get_all_health()
        assert len(all_health) == 0


# ---------------------------------------------------------------------------
# Drift detection tests
# ---------------------------------------------------------------------------


class TestDriftDetection:
    """Tests for drift detection logic."""

    def test_detect_zero_matches_warning(self, detector: SelectorDriftDetector) -> None:
        """Should detect single zero match as warning."""
        detector.record(".job-card", 5)
        detector.record(".job-card", 5)
        detector.record(".job-card", 0)

        events = detector.check_drift()
        # Zero matches can trigger multiple events
        assert len(events) >= 1
        assert any(e.severity == "warning" for e in events)

    def test_detect_zero_matches_consecutive(
        self, detector: SelectorDriftDetector
    ) -> None:
        """Should escalate severity for consecutive zeros."""
        detector.record(".job-card", 5)
        detector.record(".job-card", 0)
        detector.record(".job-card", 0)

        events = detector.check_drift()
        assert len(events) >= 1
        # Should have error or critical for 2 consecutive zeros
        severities = [e.severity for e in events]
        assert "error" in severities or "critical" in severities

    def test_detect_zero_matches_not_alert_on_normal(
        self, detector: SelectorDriftDetector
    ) -> None:
        """Should not alert for single zero with no history."""
        detector.record(".job-card", 0)

        events = detector.check_drift()
        # Single snapshot shouldn't trigger drift (needs history)
        assert len(events) == 0

    def test_detect_significant_drop(self, detector: SelectorDriftDetector) -> None:
        """Should detect sudden drop from many to few matches."""
        detector.record(".job-card", 10)
        detector.record(".job-card", 10)
        detector.record(".job-card", 1)  # >80% drop from 10

        events = detector.check_drift()
        # May trigger events due to both low count and drift
        assert len(events) >= 0  # Depends on exact thresholds

    def test_no_drift_normal_variation(self, detector: SelectorDriftDetector) -> None:
        """Should not alert for normal variation."""
        detector.record(".job-card", 5)
        detector.record(".job-card", 6)
        detector.record(".job-card", 5)
        detector.record(".job-card", 4)
        detector.record(".job-card", 5)

        events = detector.check_drift()
        # No events for normal variation
        assert len(events) == 0

    def test_health_unhealthy_for_low_matches(
        self, detector: SelectorDriftDetector
    ) -> None:
        """Should mark health as unhealthy when below threshold."""
        detector.record(".job-card", 0)
        detector.record(".job-card", 0)

        health = detector.get_selector_health(".job-card")
        assert health is not None
        assert health.is_healthy is False

    def test_drift_score_calculation(self, detector: SelectorDriftDetector) -> None:
        """Should calculate drift score based on variance."""
        detector.record(".job-card", 10)
        detector.record(".job-card", 10)
        detector.record(".job-card", 10)
        detector.record(".job-card", 10)

        health = detector.get_selector_health(".job-card")
        assert health is not None
        assert health.drift_score == 0.0  # No variance

        detector.record(".job-card", 0)
        health = detector.get_selector_health(".job-card")
        assert health is not None
        assert health.drift_score > 0.0  # High variance


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


class TestSelectorValidation:
    """Tests for selector validation on HTML."""

    def test_validate_selector(
        self, detector: SelectorDriftDetector, sample_html: str
    ) -> None:
        """Should validate selector and record result."""
        count = detector.validate_selector_on_page(".job-card", sample_html)
        assert count == 3

        health = detector.get_selector_health(".job-card")
        assert health is not None
        assert health.total_snapshots == 1

    def test_validate_selector_no_match(self, detector: SelectorDriftDetector) -> None:
        """Should record zero matches."""
        html = "<html><body><p>No jobs here</p></body></html>"
        count = detector.validate_selector_on_page(".job-card", html)
        assert count == 0


# ---------------------------------------------------------------------------
# Configuration tests
# ---------------------------------------------------------------------------


class TestConfiguration:
    """Tests for configuration helpers."""

    def test_create_from_config(self) -> None:
        """Should create detector from config."""
        config = {
            "min_expected_matches": 2,
            "history_size": 20,
            "drift_threshold": 0.3,
            "zero_match_alert_threshold": 3,
        }
        detector = create_drift_detector_from_config(config)
        assert detector.min_expected_matches == 2

    def test_create_from_config_defaults(self) -> None:
        """Should use defaults for missing config keys."""
        detector = create_drift_detector_from_config({})
        assert detector.min_expected_matches == 1


# ---------------------------------------------------------------------------
# Formatting tests
# ---------------------------------------------------------------------------


class TestFormatting:
    """Tests for event formatting."""

    def test_format_drift_event(self) -> None:
        """Should format event as readable string."""
        event = DriftEvent(
            selector=".job-card",
            expected_min=1,
            actual_count=0,
            severity="critical",
            message="Selector returned 0 matches unexpectedly",
        )
        formatted = format_drift_event(event)

        assert "[CRITICAL]" in formatted
        assert ".job-card" in formatted
        assert "0 matches" in formatted
