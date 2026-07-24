"""Selector drift detection module.

Monitors CSS selectors for unexpected changes in match counts, alerting
when selectors return 0 results unexpectedly or show significant drift
from historical patterns.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from job_board_scraper.utils.html_parser import find_elements, parse_html

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@dataclass
class SelectorSnapshot:
    """A snapshot of selector match results at a point in time.

    Attributes:
        selector: The CSS selector string.
        match_count: Number of elements matched.
        timestamp: When the snapshot was taken.
        page_url: URL of the page that was scraped.
    """

    selector: str
    match_count: int
    timestamp: datetime
    page_url: str | None = None


@dataclass
class DriftEvent:
    """A detected selector drift event.

    Attributes:
        selector: The CSS selector that drifted.
        expected_min: Minimum expected match count.
        actual_count: Actual match count observed.
        severity: One of "warning", "error", "critical".
        message: Human-readable description of the drift.
        timestamp: When the drift was detected.
    """

    selector: str
    expected_min: int
    actual_count: int
    severity: str
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class SelectorHealth:
    """Health status for a selector.

    Attributes:
        selector: The CSS selector.
        total_snapshots: Number of snapshots recorded.
        avg_match_count: Average matches over all snapshots.
        min_match_count: Minimum matches observed.
        max_match_count: Maximum matches observed.
        drift_score: Normalized drift score (0-1, higher = more volatile).
        last_drift_event: Most recent drift event, if any.
        is_healthy: Whether the selector is considered healthy.
    """

    selector: str
    total_snapshots: int = 0
    avg_match_count: float = 0.0
    min_match_count: int = 0
    max_match_count: int = 0
    drift_score: float = 0.0
    last_drift_event: DriftEvent | None = None
    is_healthy: bool = True


# ---------------------------------------------------------------------------
# Drift Detector
# ---------------------------------------------------------------------------


class SelectorDriftDetector:
    """Detects selector drift in HTML scrapers.

    Tracks selector match counts over time and alerts when:
    - Selectors return 0 results unexpectedly
    - Match counts deviate significantly from historical patterns
    - A selector consistently underperforms expectations

    Usage::

        detector = SelectorDriftDetector(
            min_expected_matches=1,
            history_size=10,
            drift_threshold=0.5,
        )

        # After scraping a page
        detector.record("div.job-card", 5, "https://example.com/jobs")

        # Check for drift
        events = detector.check_drift()
        for event in events:
            send_alert(event)

        # Get health status
        health = detector.get_selector_health("div.job-card")
    """

    def __init__(
        self,
        min_expected_matches: int = 1,
        history_size: int = 10,
        drift_threshold: float = 0.5,
        zero_match_alert_threshold: int = 2,
    ) -> None:
        """Initialize the drift detector.

        Args:
            min_expected_matches: Minimum expected matches per selector.
                Selectors below this will trigger alerts.
            history_size: Number of historical snapshots to keep per selector.
            drift_threshold: Fraction of history_size that constitutes drift.
                E.g., 0.5 means >50% change from average triggers warning.
            zero_match_alert_threshold: Consecutive zero matches before critical alert.
        """
        self._min_expected = min_expected_matches
        self._history_size = history_size
        self._drift_threshold = drift_threshold
        self._zero_threshold = zero_match_alert_threshold

        # Per-selector state: deque of snapshots
        self._snapshots: dict[str, deque[SelectorSnapshot]] = {}

        # Drift events for the current check
        self._current_events: list[DriftEvent] = []

    @property
    def min_expected_matches(self) -> int:
        """Minimum expected matches threshold."""
        return self._min_expected

    def record(
        self,
        selector: str,
        match_count: int,
        page_url: str | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        """Record a snapshot for a selector.

        Args:
            selector: CSS selector string.
            match_count: Number of elements matched.
            page_url: URL of the page (for debugging).
            timestamp: When the snapshot was taken (defaults to now).
        """
        if timestamp is None:
            timestamp = datetime.now(UTC)

        if selector not in self._snapshots:
            self._snapshots[selector] = deque(maxlen=self._history_size)

        snapshot = SelectorSnapshot(
            selector=selector,
            match_count=match_count,
            timestamp=timestamp,
            page_url=page_url,
        )

        self._snapshots[selector].append(snapshot)
        logger.debug(
            "Recorded snapshot for selector %r: %d matches",
            selector,
            match_count,
        )

    def check_drift(self) -> list[DriftEvent]:
        """Check all selectors for drift and return events.

        Returns:
            List of drift events detected since last check.
        """
        self._current_events = []

        for selector, snapshots in self._snapshots.items():
            if len(snapshots) < 2:
                continue

            latest = snapshots[-1]
            history = list(snapshots)

            # Check for zero matches
            self._check_zero_matches(selector, history, latest)

            # Check for significant drift from average
            self._check_average_drift(selector, history, latest)

            # Check for sudden drop
            self._check_sudden_drop(selector, history, latest)

        return self._current_events

    def _check_zero_matches(
        self,
        selector: str,
        history: list[SelectorSnapshot],
        latest: SelectorSnapshot,
    ) -> None:
        """Check for unexpected zero matches."""
        if latest.match_count != 0:
            return

        # Count consecutive zeros at the end
        zero_count = 0
        for snapshot in reversed(history):
            if snapshot.match_count == 0:
                zero_count += 1
            else:
                break

        if zero_count >= self._zero_threshold:
            severity = "critical"
        elif zero_count >= 2:
            severity = "error"
        else:
            severity = "warning"

        event = DriftEvent(
            selector=selector,
            expected_min=self._min_expected,
            actual_count=0,
            severity=severity,
            message=(
                f"Selector '{selector}' returned 0 matches "
                f"({zero_count} consecutive). "
                f"Expected at least {self._min_expected}."
            ),
        )

        self._current_events.append(event)
        logger.warning("Selector drift detected: %s", event.message)

    def _check_average_drift(
        self,
        selector: str,
        history: list[SelectorSnapshot],
        latest: SelectorSnapshot,
    ) -> None:
        """Check for significant deviation from historical average."""
        if len(history) < 3:
            return

        match_counts = [s.match_count for s in history[:-1]]  # Exclude latest
        avg = sum(match_counts) / len(match_counts)

        if avg == 0:
            return

        # Calculate drift as normalized difference
        drift = abs(latest.match_count - avg) / max(avg, 1)

        if drift >= self._drift_threshold and latest.match_count < self._min_expected:
            severity = "warning" if drift < 1.0 else "error"

            event = DriftEvent(
                selector=selector,
                expected_min=self._min_expected,
                actual_count=latest.match_count,
                severity=severity,
                message=(
                    f"Selector '{selector}' matched {latest.match_count} elements, "
                    f"expected {self._min_expected}+ (historical avg: {avg:.1f}). "
                    f"Drift: {drift:.1%} from average."
                ),
            )

            self._current_events.append(event)
            logger.warning("Selector drift detected: %s", event.message)

    def _check_sudden_drop(
        self,
        selector: str,
        history: list[SelectorSnapshot],
        latest: SelectorSnapshot,
    ) -> None:
        """Check for sudden drop from previous snapshot."""
        if len(history) < 2:
            return

        previous = history[-2]
        drop_ratio = (previous.match_count - latest.match_count) / max(
            previous.match_count, 1
        )

        # Alert if drop > 80% and both are below expected
        if (
            drop_ratio > 0.8
            and latest.match_count < self._min_expected
            and previous.match_count >= self._min_expected
        ):
            event = DriftEvent(
                selector=selector,
                expected_min=self._min_expected,
                actual_count=latest.match_count,
                severity="error",
                message=(
                    f"Selector '{selector}' dropped from {previous.match_count} to "
                    f"{latest.match_count} matches (80%+ drop). "
                    f"Expected at least {self._min_expected}."
                ),
            )

            self._current_events.append(event)
            logger.warning("Selector drift detected: %s", event.message)

    def get_selector_health(self, selector: str) -> SelectorHealth | None:
        """Get health status for a selector.

        Args:
            selector: CSS selector string.

        Returns:
            SelectorHealth or None if selector has no history.
        """
        if selector not in self._snapshots:
            return None

        snapshots = list(self._snapshots[selector])
        if not snapshots:
            return None

        match_counts = [s.match_count for s in snapshots]

        health = SelectorHealth(
            selector=selector,
            total_snapshots=len(snapshots),
            avg_match_count=sum(match_counts) / len(match_counts),
            min_match_count=min(match_counts),
            max_match_count=max(match_counts),
            is_healthy=min(match_counts) >= self._min_expected,
        )

        # Calculate drift score (volatility)
        if health.avg_match_count > 0:
            variance = sum((x - health.avg_match_count) ** 2 for x in match_counts)
            std_dev = (variance / len(match_counts)) ** 0.5
            health.drift_score = min(1.0, std_dev / max(health.avg_match_count, 1))

        # Find last drift event
        if selector in self._snapshots:
            for snapshot in reversed(snapshots):
                if snapshot.page_url:
                    # Check if this was a drift event
                    pass

        return health

    def get_all_health(self) -> dict[str, SelectorHealth]:
        """Get health status for all selectors.

        Returns:
            Dict mapping selector to SelectorHealth.
        """
        return {
            selector: self.get_selector_health(selector)
            for selector in self._snapshots
            if self.get_selector_health(selector) is not None
        }

    def validate_selector_on_page(
        self,
        selector: str,
        html: str,
        page_url: str | None = None,
    ) -> int:
        """Validate a selector on HTML and record the result.

        Convenience method that parses HTML, finds matches, and records.

        Args:
            selector: CSS selector to validate.
            html: HTML content.
            page_url: URL of the page (for debugging).

        Returns:
            Number of matches found.
        """
        soup = parse_html(html)
        if soup is None:
            logger.error("Failed to parse HTML for selector validation")
            return 0

        matches = find_elements(soup, selector)
        count = len(matches)

        self.record(selector, count, page_url)

        return count

    def reset_selector(self, selector: str) -> None:
        """Reset history for a selector.

        Args:
            selector: CSS selector to reset.
        """
        if selector in self._snapshots:
            self._snapshots[selector].clear()
            logger.info("Reset history for selector: %s", selector)

    def clear_all(self) -> None:
        """Clear all selector history."""
        self._snapshots.clear()
        self._current_events.clear()
        logger.info("Cleared all selector history")


# ---------------------------------------------------------------------------
# Integration helpers
# ---------------------------------------------------------------------------


def create_drift_detector_from_config(config: dict[str, Any]) -> SelectorDriftDetector:
    """Create a drift detector from configuration.

    Args:
        config: Configuration dict with keys:
            - min_expected_matches: int (default: 1)
            - history_size: int (default: 10)
            - drift_threshold: float (default: 0.5)
            - zero_match_alert_threshold: int (default: 2)

    Returns:
        Configured SelectorDriftDetector instance.
    """
    return SelectorDriftDetector(
        min_expected_matches=config.get("min_expected_matches", 1),
        history_size=config.get("history_size", 10),
        drift_threshold=config.get("drift_threshold", 0.5),
        zero_match_alert_threshold=config.get("zero_match_alert_threshold", 2),
    )


def format_drift_event(event: DriftEvent) -> str:
    """Format a drift event as a human-readable string.

    Args:
        event: DriftEvent to format.

    Returns:
        Formatted string for logging/alerting.
    """
    return (
        f"[{event.severity.upper()}] Selector Drift: {event.message}\n"
        f"  Selector: {event.selector}\n"
        f"  Expected: >= {event.expected_min} matches\n"
        f"  Actual: {event.actual_count} matches\n"
        f"  Time: {event.timestamp.isoformat()}"
    )
