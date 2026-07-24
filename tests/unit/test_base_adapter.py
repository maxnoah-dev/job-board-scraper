"""Unit tests for the base adapter protocol (adapters/base.py).

Covers:
- ExtractionStatus enum
- ExtractionResult dataclass construction and serialization
- BaseAdapter protocol runtime_checkable enforcement
"""

from __future__ import annotations

from job_board_scraper.adapters.base import (
    BaseAdapter,
    ExtractionResult,
    ExtractionStatus,
)


class TestExtractionStatus:
    """ExtractionStatus enum has three values."""

    def test_success_value(self) -> None:
        assert ExtractionStatus.SUCCESS.value == "success"

    def test_partial_value(self) -> None:
        assert ExtractionStatus.PARTIAL.value == "partial"

    def test_failed_value(self) -> None:
        assert ExtractionStatus.FAILED.value == "failed"

    def test_three_values_total(self) -> None:
        assert len(list(ExtractionStatus)) == 3


class TestExtractionResult:
    """ExtractionResult carries typed extraction outcomes."""

    def test_default_values(self) -> None:
        result = ExtractionResult()
        assert result.jobs == []
        assert result.status == ExtractionStatus.SUCCESS
        assert result.warnings == []
        assert result.error is None
        assert result.pages_fetched == 0
        assert result.requests_made == 0

    def test_can_store_jobs(self) -> None:
        result = ExtractionResult(
            jobs=[
                {"title": "Engineer", "url": "https://example.com/1"},
                {"title": "Designer", "url": "https://example.com/2"},
            ],
            status=ExtractionStatus.SUCCESS,
        )
        assert len(result.jobs) == 2
        assert result.jobs[0]["title"] == "Engineer"

    def test_can_store_warnings(self) -> None:
        result = ExtractionResult(
            warnings=["Page 3 returned empty list", "Skipped job with missing title"],
        )
        assert len(result.warnings) == 2

    def test_can_indicate_partial_failure(self) -> None:
        result = ExtractionResult(
            status=ExtractionStatus.PARTIAL,
            error=None,
            warnings=["Some jobs could not be parsed"],
            jobs=[{"title": "ok"}],
        )
        assert result.status == ExtractionStatus.PARTIAL

    def test_can_indicate_total_failure(self) -> None:
        result = ExtractionResult(
            status=ExtractionStatus.FAILED,
            error="Connection refused after 3 retries",
            jobs=[],
        )
        assert result.status == ExtractionStatus.FAILED
        assert result.error is not None
        assert len(result.jobs) == 0

    def test_model_dump_returns_dict(self) -> None:
        result = ExtractionResult(
            jobs=[{"title": "Test"}],
            status=ExtractionStatus.SUCCESS,
            warnings=["warn1"],
            pages_fetched=5,
            requests_made=10,
        )
        dumped = result.model_dump()
        assert isinstance(dumped, dict)
        assert dumped["jobs"] == [{"title": "Test"}]
        assert dumped["status"] == "success"
        assert dumped["warnings"] == ["warn1"]
        assert dumped["pages_fetched"] == 5
        assert dumped["requests_made"] == 10


class TestBaseAdapterProtocol:
    """BaseAdapter is a runtime_checkable Protocol."""

    def test_missing_methods_fails_isinstance(self) -> None:
        """An object without fetch_jobs/close is not a BaseAdapter."""

        class IncompleteAdapter:
            slug = "incomplete"
            adapter_type = "api"
            base_url = "https://example.com"

        assert not isinstance(IncompleteAdapter(), BaseAdapter)

    def test_complete_class_isinstance(self) -> None:
        """A class with all required members satisfies BaseAdapter."""

        class CompleteAdapter:
            slug = "complete"
            adapter_type = "api"
            base_url = "https://example.com"

            async def fetch_jobs(self):
                return ExtractionResult(jobs=[])

            async def close(self) -> None:
                pass

        assert isinstance(CompleteAdapter(), BaseAdapter)

    def test_protocol_enforces_slug_attribute(self) -> None:
        """An adapter without a slug attribute is not a BaseAdapter."""

        class NoSlugAdapter:
            adapter_type = "api"
            base_url = "https://example.com"

            async def fetch_jobs(self):
                return ExtractionResult(jobs=[])

            async def close(self) -> None:
                pass

        assert not isinstance(NoSlugAdapter(), BaseAdapter)
