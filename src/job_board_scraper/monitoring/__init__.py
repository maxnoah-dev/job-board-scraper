"""Monitoring package."""

from job_board_scraper.monitoring.alert_manager import (
    Alert,
    AlertManager,
    AlertSeverity,
    AlertType,
    get_alert_manager,
    log_alert_handler,
    reset_alert_manager,
)
from job_board_scraper.monitoring.selector_drift import (
    DriftEvent,
    SelectorDriftDetector,
    SelectorHealth,
    SelectorSnapshot,
    create_drift_detector_from_config,
    format_drift_event,
)

__all__ = [
    # Alert manager
    "Alert",
    "AlertManager",
    "AlertSeverity",
    "AlertType",
    "get_alert_manager",
    "log_alert_handler",
    "reset_alert_manager",
    # Selector drift
    "DriftEvent",
    "SelectorDriftDetector",
    "SelectorHealth",
    "SelectorSnapshot",
    "create_drift_detector_from_config",
    "format_drift_event",
]
