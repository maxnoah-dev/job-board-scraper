"""Async job repository.

Repository pattern implementation for job CRUD operations with
transactional upsert and idempotency. Uses SQLAlchemy 2 async sessions.

Real implementation lands in Phase 2 (P2-05..P2-06).
"""

from __future__ import annotations
