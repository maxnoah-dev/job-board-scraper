"""Adapter registry.

Plugin-style registry that loads enabled adapters from
``config/adapters/<slug>.yaml`` and maps them to their classes.
Rejects duplicate slugs and adapters whose compliance status is not
``approved``.

Real implementation lands in Phase 3 (P3-01..P3-06).
"""

from __future__ import annotations
