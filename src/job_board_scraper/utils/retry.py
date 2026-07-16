"""Retry logic.

Bounded exponential back-off with full jitter for transient HTTP
errors. Classifies errors as retryable vs. non-retryable so
authentication failures and anti-bot challenges fail fast.

Real implementation lands in Phase 3 (P3-03).
"""

from __future__ import annotations
