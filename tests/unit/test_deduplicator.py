"""Unit tests for ``etl/deduplicator.py``."""

from __future__ import annotations

from job_board_scraper.etl.deduplicator import Deduplicator, create_deduplicator
from job_board_scraper.models.job import JobRecord


def _record(url: str, title: str = "Engineer") -> JobRecord:
    return JobRecord(
        source_company_id="opswat",
        title=title,
        url=url,
        canonical_url=url,
        company_id=1,
    )


class TestDeduplicator:
    def test_deduplicate_empty(self) -> None:
        dedup = Deduplicator()
        unique, duplicates = dedup.deduplicate([])
        assert unique == []
        assert duplicates == []

    def test_deduplicate_unique(self) -> None:
        dedup = Deduplicator()
        records = [_record("https://a.com/1"), _record("https://a.com/2")]
        unique, duplicates = dedup.deduplicate(records)
        assert len(unique) == 2
        assert duplicates == []

    def test_deduplicate_duplicates(self) -> None:
        dedup = Deduplicator()
        records = [
            _record("https://a.com/1", "A"),
            _record("https://a.com/1", "B"),
            _record("https://a.com/2", "C"),
        ]
        unique, duplicates = dedup.deduplicate(records)
        assert len(unique) == 2
        assert len(duplicates) == 1
        assert "Duplicate of" in duplicates[0][1]

    def test_get_seen_urls(self) -> None:
        dedup = Deduplicator()
        records = [_record("https://a.com/1"), _record("https://a.com/2")]
        urls = dedup.get_seen_urls(records)
        assert urls == {"https://a.com/1", "https://a.com/2"}

    def test_get_seen_urls_empty(self) -> None:
        dedup = Deduplicator()
        assert dedup.get_seen_urls([]) == set()


def test_create_deduplicator() -> None:
    assert isinstance(create_deduplicator(), Deduplicator)
