"""Metrics collection.

In-process metrics collector that aggregates scrape run counters,
histograms, and gauges for dashboard export. Metrics are exposed via
structured log lines that can be parsed by log aggregators.

Real implementation lands in Phase 8 (P8-02).
"""

from __future__ import annotations
