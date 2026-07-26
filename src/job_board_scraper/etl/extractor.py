"""ETL extractor module.

Extracts job data from adapters and converts to normalized JobRecord format.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from job_board_scraper.adapters.base import ExtractionStatus
from job_board_scraper.etl.transformer import Transformer
from job_board_scraper.models.job import JobRecord, RawJobData

if TYPE_CHECKING:
    from job_board_scraper.adapters.base import BaseAdapter
    from job_board_scraper.etl.transformer import SupportsTitleTranslation

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

    def set_vilao_translator(
        self, translator: SupportsTitleTranslation | None
    ) -> None:
        """Inject or remove a Vilao translator at runtime."""
        self._transformer.set_vilao_translator(translator)

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

        if result.status is ExtractionStatus.FAILED:
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

        if self._transformer._vilao is not None:
            records, errors = await self._transformer.transform_batch_async(
                raw_jobs, company_id
            )
        else:
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
        raw_items: list[Any],
        source_company_id: str,
    ) -> list[RawJobData]:
        """Normalise adapter-emitted payload into ``RawJobData`` instances.

        Args:
            raw_items: Either raw dicts (legacy API/HTML adapters) or
                already-validated ``RawJobData`` instances (modern Greenhouse
                adapters like OPSWAT). Both shapes are accepted; the
                canonical form is what flows downstream.
            source_company_id: Company slug, used to stamp dict-shaped items
                so they pass ``RawJobData`` validation.

        Returns:
            List of validated ``RawJobData`` instances. Items that fail
            validation are skipped with a warning rather than raising.
        """
        parsed: list[RawJobData] = []
        for item in raw_items:
            try:
                if isinstance(item, RawJobData):
                    parsed.append(item)
                    continue
                if not isinstance(item, dict):
                    logger.warning(
                        "Skipping raw job item of unexpected type",
                        extra={"type": type(item).__name__},
                    )
                    continue
                item["source_company_id"] = source_company_id
                parsed.append(RawJobData(**item))
            except Exception as e:
                logger.warning(
                    "Failed to parse raw job dict",
                    extra={"error": str(e), "job_dict": item},
                )
        return parsed


def create_extractor() -> Extractor:
    """Factory function to create an extractor."""
    return Extractor()
