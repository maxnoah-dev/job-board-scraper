"""LLM integration layer.

Wraps the VilaoLLM OpenAI-compatible API to provide optional features such
as Vietnamese title translation. By default, LLM features are disabled;
callers must explicitly opt in via ``VILAO_ENABLED=true`` and a valid
``VILAO_API_KEY``.

Public API:
- :class:`VilaoClient` — typed async client with rate limiting and circuit breaker.
- :func:`translate_title_to_vietnamese` — high-level helper used by the ETL transformer.
"""

from __future__ import annotations

from job_board_scraper.llm.translator import (
    TRANSLATION_SYSTEM_PROMPT,
    TitleTranslator,
    translate_title_to_vietnamese,
)
from job_board_scraper.llm.vilao_client import (
    VilaoClient,
    VilaoClientConfig,
    VilaoError,
    VilaoUnavailableError,
)

__all__ = [
    "TitleTranslator",
    "TRANSLATION_SYSTEM_PROMPT",
    "translate_title_to_vietnamese",
    "VilaoClient",
    "VilaoClientConfig",
    "VilaoError",
    "VilaoUnavailableError",
]
