"""Scheduled job definitions.

Typed APScheduler job functions registered at startup. Each job
has a descriptive ID, a run lock, and an optional timeout.

Real implementation lands in Phase 8 (P8-07).
"""

from __future__ import annotations
