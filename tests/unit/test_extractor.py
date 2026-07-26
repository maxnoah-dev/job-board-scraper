"""Unit tests for the ETL Extractor (src/job_board_scraper/etl/extractor.py).

Regression coverage for the AttributeError bug where adapters constructed
``ExtractionResult(status="failed")`` with a plain string but the extractor
read ``result.status.value``. That mismatch made every company return zero
jobs because the pipeline crashed before transformation.
"""

from __future__ import annotations

from typing import Any

import pytest

from job_board_scraper.adapters.base import ExtractionResult, ExtractionStatus
from job_board_scraper.etl.extractor import Extractor


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