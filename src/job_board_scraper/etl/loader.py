"""Data loading.

Transactional upsert of normalized JobRecord objects into the database.
Handles duplicates idempotently and emits scrape run summaries.

Real implementation lands in Phase 4 (P4-04).
"""

from __future__ import annotations
