"""Deduplicator module.

Handles URL-based deduplication for jobs within a scrape run.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from job_board_scraper.models.job import JobRecord

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class Deduplicator:
    """Deduplicates job records based on canonical URLs.

    Ensures that within a single scrape run, each unique canonical URL
    appears only once. This is a first-pass dedup - the database
    unique constraint handles cross-run deduplication.
    """

    def deduplicate(
        self,
        records: list[JobRecord],
    ) -> tuple[list[JobRecord], list[tuple[JobRecord, str]]]:
        """Remove duplicate records based on canonical URL.

        Args:
            records: List of job records to deduplicate

        Returns:
            Tuple of (unique records, duplicates with reason)
        """
        if not records:
            return [], []

        seen: dict[str, JobRecord] = {}
        duplicates: list[tuple[JobRecord, str]] = []

        for record in records:
            url = record.canonical_url
            if url in seen:
                existing = seen[url]
                duplicates.append((record, f"Duplicate of {existing.title}"))
                logger.debug(
                    "Duplicate job skipped",
                    extra={"url": url, "title": record.title},
                )
            else:
                seen[url] = record

        unique = list(seen.values())

        if duplicates:
            logger.info(
                "Duplicates removed",
                extra={
                    "total": len(records),
                    "unique": len(unique),
                    "dupes": len(duplicates),
                },
            )

        return unique, duplicates

    def get_seen_urls(self, records: list[JobRecord]) -> set[str]:
        """Extract canonical URLs from records.

        Args:
            records: List of job records

        Returns:
            Set of canonical URLs
        """
        return {record.canonical_url for record in records}


def create_deduplicator() -> Deduplicator:
    """Factory function to create a deduplicator."""
    return Deduplicator()
