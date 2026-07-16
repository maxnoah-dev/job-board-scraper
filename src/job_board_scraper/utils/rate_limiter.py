"""Per-origin rate limiter.

Async semaphore-based rate limiter that enforces per-source
min-interval delays and per-origin concurrency caps. Integrates with
the HTTP client wrapper so requests are automatically spaced.

Real implementation lands in Phase 3 (P3-04).
"""

from __future__ import annotations
