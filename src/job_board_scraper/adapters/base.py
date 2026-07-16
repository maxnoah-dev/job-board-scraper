"""Abstract base adapter.

All company adapters inherit from ``BaseAdapter``. Defines the contract:
``fetch_jobs()`` → list of raw job dicts and typed ``ExtractionResult``.

Real implementation lands in Phase 3 (P3-01..P3-06).
"""

from __future__ import annotations
