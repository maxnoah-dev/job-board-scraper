"""Title translation helper built on top of :class:`VilaoClient`.

Provides a thin async function ``translate_title_to_vietnamese`` plus a
cached ``TitleTranslator`` wrapper. Translation is best-effort: when the
client is unavailable, the function returns ``None`` so the calling ETL
pipeline can continue without blocking on LLM outages.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from job_board_scraper.llm.vilao_client import (
    VilaoClient,
    VilaoError,
    VilaoUnavailableError,
)

if TYPE_CHECKING:
    pass


TRANSLATION_SYSTEM_PROMPT = (
    "Bạn là chuyên gia dịch tiêu đề việc làm IT sang tiếng Việt. "
    "Chỉ trả về bản dịch, không giải thích."
)


def _fingerprint(title: str) -> str:
    """Return a stable SHA-256 hex digest used as the cache key."""
    return hashlib.sha256(title.strip().lower().encode("utf-8")).hexdigest()


async def translate_title_to_vietnamese(
    title: str,
    vilao: VilaoClient,
    *,
    cache: dict[str, str] | None = None,
) -> str | None:
    """Translate a job title to Vietnamese via Vilao.

    Args:
        title: The original title (English or otherwise).
        vilao: A configured :class:`VilaoClient` instance.
        cache: Optional dict used as a process-local cache. When provided,
            repeated calls with the same title are not billed.

    Returns:
        The translated Vietnamese title, or ``None`` if the client is
        unavailable or the request fails.
    """
    if not title or not title.strip():
        return None
    if not vilao.is_available:
        return None

    key = _fingerprint(title)
    if cache is not None and key in cache:
        return cache[key]

    try:
        translated = await vilao.chat(
            prompt=title,
            system=TRANSLATION_SYSTEM_PROMPT,
            temperature=0.0,
            max_tokens=128,
        )
    except (VilaoUnavailableError, VilaoError):
        return None

    if not translated:
        return None

    if cache is not None:
        cache[key] = translated
    return translated


class TitleTranslator:
    """Stateful wrapper that bundles a Vilao client, cache, and call counter."""

    def __init__(self, vilao: VilaoClient) -> None:
        self._vilao = vilao
        self._cache: dict[str, str] = {}
        self._calls = 0
        self._hits = 0

    @property
    def call_count(self) -> int:
        return self._calls

    @property
    def cache_hits(self) -> int:
        return self._hits

    async def translate(self, title: str) -> str | None:
        key = _fingerprint(title)
        if key in self._cache:
            self._hits += 1
            return self._cache[key]
        if not self._vilao.is_available:
            return None
        self._calls += 1
        result = await translate_title_to_vietnamese(
            title, self._vilao, cache=self._cache
        )
        if result is None:
            return None
        self._cache[key] = result
        return result
