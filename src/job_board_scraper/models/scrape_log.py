"""Scrape log domain model.

Pydantic v2 schema for a scrape run and scrape attempt. Tracks
started_at / completed_at, status, job counts, error messages, and duration.

Real implementation lands in Phase 2 (P2-01..P2-02).
"""

from __future__ import annotations
