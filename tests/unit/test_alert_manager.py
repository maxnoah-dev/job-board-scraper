"""Tests for alert manager."""

from __future__ import annotations

import pytest

from job_board_scraper.monitoring.alert_manager import (
    Alert,
    AlertManager,
    AlertSeverity,
    AlertType,
    get_alert_manager,
    log_alert_handler,
    reset_alert_manager,
)


@pytest.fixture
def manager() -> AlertManager:
    """Create a fresh alert manager."""
    return AlertManager()


@pytest.fixture(autouse=True)
def reset_manager():
    """Reset global manager before each test."""
    reset_alert_manager()
    yield
    reset_alert_manager()


# ---------------------------------------------------------------------------
# Alert dataclass tests
# ---------------------------------------------------------------------------


class TestAlert:
    """Tests for Alert dataclass."""

    def test_create_alert(self) -> None:
        """Should create an alert with all fields."""
        alert = Alert(
            alert_type=AlertType.SCRAPE_FAILURE,
            severity=AlertSeverity.ERROR,
            source="opswat",
            message="Failed to fetch jobs",
        )
        assert alert.alert_type == AlertType.SCRAPE_FAILURE
        assert alert.severity == AlertSeverity.ERROR
        assert alert.source == "opswat"
        assert alert.acknowledged is False

    def test_alert_to_dict(self) -> None:
        """Should convert alert to dictionary."""
        alert = Alert(
            alert_type=AlertType.SELECTOR_DRIFT,
            severity=AlertSeverity.WARNING,
            source="techcorp",
            message="Selector drifted",
        )
        d = alert.to_dict()
        assert d["alert_type"] == "selector_drift"
        assert d["severity"] == "warning"
        assert d["source"] == "techcorp"


# ---------------------------------------------------------------------------
# AlertManager tests
# ---------------------------------------------------------------------------


class TestAlertManager:
    """Tests for AlertManager."""

    def test_register_handler(self, manager: AlertManager) -> None:
        """Should register a handler."""
        called = []

        def handler(alert: Alert) -> None:
            called.append(alert)

        manager.register_handler(handler)
        assert len(manager._handlers) == 1

    def test_unregister_handler(self, manager: AlertManager) -> None:
        """Should unregister a handler."""

        def handler(alert: Alert) -> None:
            pass

        manager.register_handler(handler)
        manager.unregister_handler(handler)
        assert len(manager._handlers) == 0

    def test_send_alert(self, manager: AlertManager) -> None:
        """Should send alert to handlers."""
        received = []

        def handler(alert: Alert) -> None:
            received.append(alert)

        manager.register_handler(handler)
        alert = manager.alert(
            AlertType.SCRAPE_FAILURE,
            AlertSeverity.ERROR,
            "opswat",
            "Test message",
        )

        assert len(received) == 1
        assert received[0] == alert
        assert len(manager._alerts) == 1

    def test_handler_exception_doesnt_crash(self, manager: AlertManager) -> None:
        """Should handle handler exceptions gracefully."""

        def bad_handler(alert: Alert) -> None:
            raise Exception("Handler error")

        manager.register_handler(bad_handler)
        # Should not raise
        alert = manager.alert(
            AlertType.SCRAPE_FAILURE,
            AlertSeverity.ERROR,
            "opswat",
            "Test",
        )
        assert alert is not None

    def test_get_active_alerts(self, manager: AlertManager) -> None:
        """Should return unacknowledged alerts."""
        manager.alert(
            AlertType.SCRAPE_FAILURE, AlertSeverity.ERROR, "opswat", "Error 1"
        )
        manager.alert(AlertType.ZERO_JOBS, AlertSeverity.CRITICAL, "vancity", "Zero")
        manager._alerts[0].acknowledged = True

        active = manager.get_active_alerts()
        assert len(active) == 1
        assert active[0].source == "vancity"

    def test_get_active_alerts_filter_type(self, manager: AlertManager) -> None:
        """Should filter by alert type."""
        manager.alert(AlertType.SCRAPE_FAILURE, AlertSeverity.ERROR, "opswat", "Error")
        manager.alert(AlertType.ZERO_JOBS, AlertSeverity.CRITICAL, "vancity", "Zero")

        active = manager.get_active_alerts(alert_type=AlertType.SCRAPE_FAILURE)
        assert len(active) == 1
        assert active[0].alert_type == AlertType.SCRAPE_FAILURE

    def test_get_active_alerts_filter_source(self, manager: AlertManager) -> None:
        """Should filter by source."""
        manager.alert(AlertType.SCRAPE_FAILURE, AlertSeverity.ERROR, "opswat", "Error")
        manager.alert(AlertType.SCRAPE_FAILURE, AlertSeverity.ERROR, "vancity", "Error")

        active = manager.get_active_alerts(source="opswat")
        assert len(active) == 1
        assert active[0].source == "opswat"

    def test_acknowledge_alert(self, manager: AlertManager) -> None:
        """Should mark alert as acknowledged."""
        alert = manager.alert(
            AlertType.SCRAPE_FAILURE, AlertSeverity.ERROR, "opswat", "Error"
        )
        assert alert.acknowledged is False

        manager.acknowledge(alert)
        assert alert.acknowledged is True

    def test_clear_acknowledged(self, manager: AlertManager) -> None:
        """Should remove acknowledged alerts."""
        manager.alert(AlertType.SCRAPE_FAILURE, AlertSeverity.ERROR, "opswat", "1")
        manager.alert(AlertType.ZERO_JOBS, AlertSeverity.CRITICAL, "vancity", "2")
        manager._alerts[0].acknowledged = True

        removed = manager.clear_acknowledged()
        assert removed == 1
        assert len(manager._alerts) == 1


# ---------------------------------------------------------------------------
# Alert type specific handlers
# ---------------------------------------------------------------------------


class TestAlertTypeHandlers:
    """Tests for specific alert type handlers."""

    def test_handle_selector_drift(self, manager: AlertManager) -> None:
        """Should handle selector drift events."""
        from job_board_scraper.monitoring.selector_drift import DriftEvent

        event = DriftEvent(
            selector=".job-card",
            expected_min=1,
            actual_count=0,
            severity="error",
            message="Selector returned 0 matches",
        )

        alert = manager.handle_selector_drift(event, "techcorp")

        assert alert.alert_type == AlertType.SELECTOR_DRIFT
        assert alert.severity == AlertSeverity.ERROR
        assert alert.source == "techcorp"
        # Selector is in details, not message
        assert alert.details["selector"] == ".job-card"
        assert "Selector drift detected" in alert.message

    def test_handle_scrape_failure(self, manager: AlertManager) -> None:
        """Should handle scrape failure."""
        alert = manager.handle_scrape_failure("opswat", "Connection timeout")

        assert alert.alert_type == AlertType.SCRAPE_FAILURE
        assert alert.severity == AlertSeverity.ERROR
        assert alert.source == "opswat"

    def test_handle_scrape_failure_partial(self, manager: AlertManager) -> None:
        """Should downgrade severity for partial failures."""
        alert = manager.handle_scrape_failure(
            "opswat", "Some jobs fetched", is_partial=True
        )
        assert alert.severity == AlertSeverity.WARNING

    def test_handle_zero_jobs(self, manager: AlertManager) -> None:
        """Should handle zero jobs alert."""
        alert = manager.handle_zero_jobs("opswat", 0)

        assert alert.alert_type == AlertType.ZERO_JOBS
        assert alert.severity == AlertSeverity.CRITICAL
        assert "Zero jobs" in alert.message

    def test_handle_rate_limit(self, manager: AlertManager) -> None:
        """Should handle rate limit."""
        alert = manager.handle_rate_limit("opswat")

        assert alert.alert_type == AlertType.RATE_LIMIT
        assert alert.severity == AlertSeverity.WARNING

    def test_handle_anti_bot(self, manager: AlertManager) -> None:
        """Should handle anti-bot detection."""
        alert = manager.handle_anti_bot("tiktok")

        assert alert.alert_type == AlertType.ANTI_BOT
        assert alert.severity == AlertSeverity.CRITICAL


# ---------------------------------------------------------------------------
# Global manager tests
# ---------------------------------------------------------------------------


class TestGlobalManager:
    """Tests for global alert manager."""

    def test_get_alert_manager(self) -> None:
        """Should return singleton instance."""
        m1 = get_alert_manager()
        m2 = get_alert_manager()
        assert m1 is m2

    def test_reset_alert_manager(self) -> None:
        """Should reset singleton."""
        m1 = get_alert_manager()
        reset_alert_manager()
        m2 = get_alert_manager()
        assert m1 is not m2


# ---------------------------------------------------------------------------
# Default handlers tests
# ---------------------------------------------------------------------------


class TestDefaultHandlers:
    """Tests for default alert handlers."""

    def test_log_alert_handler(self, caplog) -> None:
        """Should log alert at appropriate level."""
        import logging

        alert = Alert(
            alert_type=AlertType.SCRAPE_FAILURE,
            severity=AlertSeverity.ERROR,
            source="opswat",
            message="Test error",
        )

        with caplog.at_level(logging.ERROR):
            log_alert_handler(alert)

        assert "opswat" in caplog.text
        assert "Test error" in caplog.text
