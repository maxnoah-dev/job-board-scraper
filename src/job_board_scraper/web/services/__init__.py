"""Web services package."""

from job_board_scraper.web.services.scrape_trigger import (
    ScrapeTrigger,
    ScrapeTriggerError,
    get_trigger,
)

__all__ = [
    "ScrapeTrigger",
    "ScrapeTriggerError",
    "get_trigger",
]
