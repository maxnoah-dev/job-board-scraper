"""APScheduler setup.

APScheduler wrapper that reuses the same application service as the
one-shot CLI entry point. The wrapper is active only when
``SCHEDULER_ENABLED=true``; production uses an external scheduler
instead (see ADR-0006).

Real implementation lands in Phase 8 (P8-07).
"""

from __future__ import annotations
