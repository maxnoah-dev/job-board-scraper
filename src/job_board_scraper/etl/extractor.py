"""Extraction orchestration.

Manages the adapter lifecycle: resolve, instantiate, fetch, and
translate raw data into normalized JobRecord objects.

Real implementation lands in Phase 3 (P3-01..P3-06).
"""

from __future__ import annotations
