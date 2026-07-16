"""CLI entry point.

One-shot scrape invocation that runs the full ETL pipeline and exits
with ``success`` / ``partial`` / ``failed`` exit codes per
``docs/adr/0006-scheduler-export.md``.

Real implementation lands in Phase 4 (P4-05).
"""

from __future__ import annotations

import sys


def main() -> int:
    """Run a single ETL scrape and exit with status code."""
    raise NotImplementedError("P4-05 not started")


if __name__ == "__main__":
    sys.exit(main())
