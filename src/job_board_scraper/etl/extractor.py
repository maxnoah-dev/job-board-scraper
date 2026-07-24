"""ETL extractor module.

Extracts job data from adapters and converts to normalized JobRecord format.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from job_board_scraper.etl.transformer import Transformer
from job_board_scraper.models.job import JobRecord, RawJobData

if TYPE_CHECKING:
    from job_board_scraper.adapters.base import BaseAdapter

logger = logging.getLogger(__name__)


class Extractor:
    """Extracts and transforms job data from adapters.

    Coordinates:
    1. Calling adapter.fetch_jobs()
    2. Converting raw dict results to RawJobData Pydantic models
    3. Transforming to canonical JobRecord via Transformer
    """

    def __init__(self) -> None:
        self._transformer = Transformer()

    async def extract_from_adapter(
        self,
        adapter: BaseAdapter,
        company_id: int,
    ) -> tuple[list[JobRecord], list[tuple[RawJobData, Exception]]]:
        """Extract jobs from a single adapter.

        Args:
            adapter: The adapter to extract from
            company_id: Company ID from database

        Returns:
            Tuple of (successful records, failed raw jobs with errors)
        """
        logger.debug("Extracting jobs from adapter", extra={"adapter": adapter.slug})

        result = await adapter.fetch_jobs()

        if result.status.value == "failed":
            logger.error(
                "Adapter extraction failed",
                extra={"adapter": adapter.slug, "error": result.error},
            )
            return [], []

        if result.warnings:
            logger.warning(
                "Adapter extraction had warnings",
                extra={"adapter": adapter.slug, "warnings": result.warnings},
            )

        raw_jobs = self._parse_raw_jobs(result.jobs, adapter.slug)

        records, errors = self._transformer.transform_batch(raw_jobs, company_id)

        logger.info(
            "Extraction complete",
            extra={
                "adapter": adapter.slug,
                "raw_count": len(result.jobs),
                "parsed_count": len(raw_jobs),
                "records_count": len(records),
                "errors_count": len(errors),
            },
        )

        return records, errors

    def _parse_raw_jobs(
        self,
        raw_dicts: list[dict],
        source_company_id: str,
    ) -> list[RawJobData]:
        """Parse raw job dictionaries into RawJobData models.

        Args:
            raw_dicts: List of raw job dictionaries from adapter
            source_company_id: Company slug for context

        Returns:
            List of validated RawJobData instances
        """
        parsed: list[RawJobData] = []
        for job_dict in raw_dicts:
            try:
                job_dict["source_company_id"] = source_company_id
                raw = RawJobData(**job_dict)
                parsed.append(raw)
            except Exception as e:
                logger.warning(
                    "Failed to parse raw job dict",
                    extra={"error": str(e), "job_dict": job_dict},
                )
        return parsed


def create_extractor() -> Extractor:
    """Factory function to create an extractor."""
    return Extractor()
