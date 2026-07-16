"""Anomaly detectors.

Rule-based detectors that emit alerts when patterns indicate data
quality issues: zero-job scrape, selector drift, anti-bot challenges,
and unusual error rate spikes.

Real implementation lands in Phase 8 (P8-04).
"""

from __future__ import annotations
