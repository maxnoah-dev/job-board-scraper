"""Unit tests for the ETL Extractor (src/job_board_scraper/etl/extractor.py).

Regression coverage for two related bugs:

1. ``AttributeError`` on ``result.status.value`` when adapters constructed
   ``ExtractionResult(status="failed")`` with a plain string. The extractor
   must tolerate both enum and string status values.
2. Real adapters (e.g. OPSWAT) populate ``ExtractionResult.jobs`` with
   already-validated ``RawJobData`` Pydantic models, not raw dicts. The
   extractor must accept both shapes so the pipeline can store jobs.
"""

from __future__ import annotations

from typing import Any

import pytest

from job_board_scraper.adapters.base import ExtractionResult, ExtractionStatus
from job_board_scraper.etl.extractor import Extractor
from job_board_scraper.models.job import RawJobData


class StubAdapter:
    """Minimal adapter double that lets us inject any ExtractionResult."""

    def __init__(self, slug: str, result: ExtractionResult) -> None:
        self.slug = slug
        self.adapter_type = "stub"
        self.base_url = "https://example.test"
        self._result = result
        self.closed = False

    async def fetch_jobs(self) -> ExtractionResult:
        return self._result

    async def close(self) -> None:
        self.closed = True


def _raw_job(title: str = "Software Engineer") -> dict[str, Any]:
    return {
        "source_company_id": "stub-co",
        "title": title,
        "url": "https://example.test/jobs/123",
    }


@pytest.mark.unit
class TestExtractorStatusHandling:
    """Regression tests: status must be comparable regardless of input shape."""

    @pytest.mark.asyncio
    async def test_extract_handles_enum_failed_status(self) -> None:
        # Arrange
        adapter = StubAdapter(
            slug="ok-enum",
            result=ExtractionResult(
                jobs=[],
                status=ExtractionStatus.FAILED,
                error="auth denied",
            ),
        )
        extractor = Extractor()

        # Act — must NOT raise
        records, errors = await extractor.extract_from_adapter(adapter, company_id=1)

        # Assert: a failed extraction returns empty lists, not a crash
        assert records == []
        assert errors == []

    @pytest.mark.asyncio
    async def test_extract_handles_string_failed_status(self) -> None:
        """Adapters constructed the result with status='failed' (str) historically.

        The extractor must tolerate both shapes so older protocol code paths
        cannot poison the pipeline.
        """
        # Arrange
        adapter = StubAdapter(
            slug="legacy-str",
            result=ExtractionResult(
                jobs=[],
                status="failed",  # type: ignore[arg-type]
                error="auth denied",
            ),
        )
        extractor = Extractor()

        # Act — must NOT raise AttributeError
        records, errors = await extractor.extract_from_adapter(adapter, company_id=1)

        # Assert
        assert records == []
        assert errors == []

    @pytest.mark.asyncio
    async def test_extract_handles_string_partial_status(self) -> None:
        adapter = StubAdapter(
            slug="legacy-partial",
            result=ExtractionResult(
                jobs=[_raw_job()],
                status="partial",  # type: ignore[arg-type]
                warnings=["one page failed"],
            ),
        )
        extractor = Extractor()

        records, errors = await extractor.extract_from_adapter(adapter, company_id=42)

        assert len(records) == 1
        assert errors == []

    @pytest.mark.asyncio
    async def test_extract_handles_string_success_status(self) -> None:
        adapter = StubAdapter(
            slug="legacy-success",
            result=ExtractionResult(
                jobs=[_raw_job(title="Data Engineer")],
                status="success",  # type: ignore[arg-type]
            ),
        )
        extractor = Extractor()

        records, errors = await extractor.extract_from_adapter(adapter, company_id=7)

        assert len(records) == 1
        assert records[0].title == "Data Engineer"
        assert records[0].company_id == 7
        assert errors == []


@pytest.mark.unit
class TestExtractorHappyPath:
    @pytest.mark.asyncio
    async def test_transforms_raw_jobs_into_records(self) -> None:
        adapter = StubAdapter(
            slug="happy",
            result=ExtractionResult(
                jobs=[
                    _raw_job(title="Backend Engineer"),
                    _raw_job(title="Frontend Engineer"),
                ],
                status=ExtractionStatus.SUCCESS,
            ),
        )
        extractor = Extractor()

        records, errors = await extractor.extract_from_adapter(adapter, company_id=3)

        assert len(records) == 2
        assert errors == []
        titles = {r.title for r in records}
        assert titles == {"Backend Engineer", "Frontend Engineer"}


@pytest.mark.unit
class TestExtractorRawJobDataItems:
    """Real adapters (OPSWAT, Vancity, ...) put ``RawJobData`` objects into
    ``ExtractionResult.jobs`` rather than raw dicts. The extractor must accept
    both shapes; otherwise every scrape silently drops 100% of jobs.
    """

    @pytest.mark.asyncio
    async def test_accepts_rawjobdata_items_in_result_jobs(self) -> None:
        raw_items = [
            RawJobData(
                source_company_id="opswat",
                title="Senior Backend Engineer",
                url="https://www.opswat.com/jobs/1",
                location="Ho Chi Minh City",
                source_job_id="1",
                date_posted="2026-07-15",
            ),
            RawJobData(
                source_company_id="opswat",
                title="Frontend Engineer",
                url="https://www.opswat.com/jobs/2",
                location="Remote",
                source_job_id="2",
                date_posted="2026-07-14",
            ),
        ]
        adapter = StubAdapter(
            slug="opswat",
            result=ExtractionResult(
                jobs=raw_items,  # type: ignore[arg-type]
                status=ExtractionStatus.SUCCESS,
            ),
        )
        extractor = Extractor()

        records, errors = await extractor.extract_from_adapter(adapter, company_id=1)

        assert errors == []
        assert len(records) == 2
        titles = {r.title for r in records}
        assert titles == {"Senior Backend Engineer", "Frontend Engineer"}
        assert all(r.company_id == 1 for r in records)

    @pytest.mark.asyncio
    async def test_accepts_mixed_dict_and_rawjobdata_items(self) -> None:
        """Some adapters may return dicts, others return RawJobData. The
        extractor must normalise both into ``JobRecord`` without crashing."""
        raw_item = RawJobData(
            source_company_id="opswat",
            title="Already Parsed",
            url="https://www.opswat.com/jobs/3",
            source_job_id="3",
        )
        dict_item = {
            "source_company_id": "opswat",
            "title": "Still Dict",
            "url": "https://www.opswat.com/jobs/4",
            "source_job_id": "4",
        }
        adapter = StubAdapter(
            slug="opswat",
            result=ExtractionResult(
                jobs=[raw_item, dict_item],  # type: ignore[list-item]
                status=ExtractionStatus.SUCCESS,
            ),
        )
        extractor = Extractor()

        records, errors = await extractor.extract_from_adapter(adapter, company_id=2)

        assert errors == []
        assert len(records) == 2
        titles = {r.title for r in records}
        assert titles == {"Already Parsed", "Still Dict"}
