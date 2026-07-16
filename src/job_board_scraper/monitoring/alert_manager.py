"""Alert management.

Observer-pattern alert dispatcher that notifies email, Slack, and log
sinks when events cross severity thresholds. Each sink is isolated so
a failure in one channel does not block the others.

Real implementation lands in Phase 8 (P8-03..P8-04).
"""

from __future__ import annotations
