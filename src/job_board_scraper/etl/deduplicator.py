"""Deduplication logic.

Deterministic deduplication of incoming job records against the database
using the unique constraint on (company_id, canonical_url). Also handles
stale job reconciliation per ADR-0004.

Real implementation lands in Phase 2 (P2-06) and Phase 4 (P4-03).
"""

from __future__ import annotations
