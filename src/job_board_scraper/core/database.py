"""Database connection management.

SQLAlchemy 2 async engine for SQLite (local/test) and PostgreSQL (production).
Connection pooling, session factory, and transaction helpers.

Real implementation lands in Phase 2 (P2-03..P2-04).
"""

from __future__ import annotations
