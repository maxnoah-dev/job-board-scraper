"""ETL Transformer for normalizing job data.

Transforms RawJobData from adapters into canonical JobRecord.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from job_board_scraper.models.job import (
    JobRecord,
    JobStatus,
    RawJobData,
    canonicalize_url,
)

if TYPE_CHECKING:
    pass


class Transformer:
    """Transforms RawJobData into canonical JobRecord.

    Applies the following transformations:
    1. Canonicalize URL (ADR-0003)
    2. Normalize date to UTC (ADR-0005)
    3. Validate required fields
    4. Set defaults
    """

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
