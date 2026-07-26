"""ETL Transformer for normalizing job data.

Transforms RawJobData from adapters into canonical JobRecord.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Protocol

from job_board_scraper.models.job import (
    JobRecord,
    JobStatus,
    RawJobData,
    canonicalize_url,
)

if TYPE_CHECKING:
    pass


logger = logging.getLogger(__name__)


class SupportsTitleTranslation(Protocol):
    """Minimal protocol for the Vilao translator.

    Allows the transformer to call ``translate`` without importing the
    concrete ``TitleTranslator`` (which pulls in the OpenAI SDK).
    """

    async def translate(self, title: str) -> str | None:  # pragma: no cover
        ...


class Transformer:
    """Transforms RawJobData into canonical JobRecord.

    Applies the following transformations:
    1. Canonicalize URL (ADR-0003)
    2. Normalize date to UTC (ADR-0005)
    3. Validate required fields
    4. Set defaults
    5. Optional: Vietnamese title translation via Vilao LLM
    """

    def __init__(self, vilao_translator: SupportsTitleTranslation | None = None) -> None:
        self._vilao = vilao_translator

    def set_vilao_translator(
        self, translator: SupportsTitleTranslation | None
    ) -> None:
        """Inject or remove a Vilao translator (used by the pipeline)."""
        self._vilao = translator

    async def transform_async(
        self, raw: RawJobData, company_id: int
    ) -> JobRecord:
        """Async transform — used when Vilao is enabled.

        Falls back to the synchronous ``transform`` when no translator is set.
        """
        record = self.transform(raw, company_id)
        if self._vilao is None:
            return record
        try:
            title_vi = await self._vilao.translate(raw.title)
        except Exception:  # noqa: BLE001 — never let LLM crash the pipeline
            logger.exception("Vilao translation failed for %r", raw.title)
            return record
        return record.model_copy(update={"title_vi": title_vi})

    def transform(self, raw: RawJobData, company_id: int) -> JobRecord:
        """Transform a raw job into a canonical record.

        Args:
            raw: Raw job data from adapter
            company_id: Company ID from database

        Returns:
            Canonical JobRecord ready for storage
        """
        # Canonicalize the URL
        try:
            canonical = canonicalize_url(raw.url)
        except ValueError:
            # Use original URL if canonicalization fails
            canonical = raw.url

        # Normalize date to UTC (handled by JobRecord validator)
        date_posted = raw.date_posted

        # Create canonical record
        return JobRecord(
            company_id=company_id,
            title=raw.title,
            location=raw.location or "Remote",
            url=raw.url,
            canonical_url=canonical,
            date_posted=date_posted,
            status=JobStatus.open,
            source_job_id=raw.source_job_id,
            raw_data=raw.raw_data,
        )

    async def transform_batch_async(
        self,
        raw_jobs: list[RawJobData],
        company_id: int,
    ) -> tuple[list[JobRecord], list[tuple[RawJobData, Exception]]]:
        """Async batch transform that awaits Vilao translations in parallel."""
        records: list[JobRecord] = []
        errors: list[tuple[RawJobData, Exception]] = []

        coros = [self.transform_async(raw, company_id) for raw in raw_jobs]
        results = await asyncio.gather(*coros, return_exceptions=True)
        for raw, outcome in zip(raw_jobs, results, strict=True):
            if isinstance(outcome, Exception):
                errors.append((raw, outcome))
            else:
                records.append(outcome)
        return records, errors

    def transform_batch(
        self,
        raw_jobs: list[RawJobData],
        company_id: int,
    ) -> tuple[list[JobRecord], list[tuple[RawJobData, Exception]]]:
        """Transform a batch of raw jobs.

        Args:
            raw_jobs: List of raw job data
            company_id: Company ID

        Returns:
            Tuple of (successful records, failed raw jobs with errors)
        """
        records: list[JobRecord] = []
        errors: list[tuple[RawJobData, Exception]] = []

        for raw in raw_jobs:
            try:
                record = self.transform(raw, company_id)
                records.append(record)
            except Exception as e:
                errors.append((raw, e))

        return records, errors


def create_transformer() -> Transformer:
    """Factory function to create a transformer."""
    return Transformer()
