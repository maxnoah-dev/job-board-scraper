"""Adapters package.

Plugin system for job scraper adapters.
"""

from job_board_scraper.adapters.base import (
    BaseAdapter,
    BaseAdapterImpl,
    ExtractionResult,
    ExtractionStatus,
)
from job_board_scraper.adapters.protocols.html_adapter import (
    HtmlAdapter,
    create_job_listing_config,
    extract_date_from_string,
)

__all__ = [
    "BaseAdapter",
    "BaseAdapterImpl",
    "ExtractionResult",
    "ExtractionStatus",
    "HtmlAdapter",
    "create_job_listing_config",
    "extract_date_from_string",
]
