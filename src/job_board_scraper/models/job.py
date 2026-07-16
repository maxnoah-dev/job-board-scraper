"""Job domain model.

Pydantic v2 schema for a normalized job record and its raw source variant.
Includes URL canonicalization, date parsing, and status validation.

Real implementation lands in Phase 2 (P2-01..P2-02).
"""

from __future__ import annotations
