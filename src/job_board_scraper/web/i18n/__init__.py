"""Internationalization (i18n) support for the web dashboard.

Provides a simple JSON-dictionary based translation system with English
and Vietnamese locales. Designed to be lightweight: no external i18n
library, no .po/.mo files, just nested JSON keyed by dotted paths.
"""

from __future__ import annotations

from job_board_scraper.web.i18n.translations import (
    DEFAULT_LOCALE,
    SUPPORTED_LOCALES,
    get_translation,
    get_translator,
)

__all__ = [
    "SUPPORTED_LOCALES",
    "DEFAULT_LOCALE",
    "get_translation",
    "get_translator",
]
