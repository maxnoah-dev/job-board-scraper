"""job-board-scraper.

Async ETL pipeline that scrapes job listings from 11+ company career
pages and aggregates them into a single normalized database. Phase 1
only ships the package skeleton and quality tooling; the actual ETL
contract lands in Phase 2 onwards (see ``docs/ROADMAP.md``).
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
