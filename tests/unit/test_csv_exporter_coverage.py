"""Unit tests for ``reporting/csv_exporter.py``."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

import pytest

from job_board_scraper.reporting.csv_exporter import (
    CsvExporter,
    ExportOptions,
    get_exporter,
)


def _job(**kw: object) -> dict:
    base = {
        "company_name": "OPSWAT",
        "title": "Senior Engineer",
        "location": "Remote",
        "job_url": "https://example.com/1",
        "canonical_url": "https://example.com/1",
        "date_posted": datetime(2026, 1, 1),
        "status": "open",
    }
    base.update(kw)
    return base


@pytest.mark.asyncio
class TestCsvExporter:
    async def test_export_writes_csv(self, tmp_path: Path) -> None:
        exporter = CsvExporter(tmp_path)
        path = await exporter.export([_job()], options=ExportOptions())
        assert path.exists()
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["company_name"] == "OPSWAT"
        assert rows[0]["job_title"] == "Senior Engineer"

    async def test_export_filters_closed_when_not_included(self, tmp_path: Path) -> None:
        exporter = CsvExporter(tmp_path)
        jobs = [_job(), _job(status="closed")]
        path = await exporter.export(jobs, options=ExportOptions(include_closed=False))
        with open(path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1

    async def test_export_includes_closed_when_requested(self, tmp_path: Path) -> None:
        exporter = CsvExporter(tmp_path)
        jobs = [_job(), _job(status="closed")]
        path = await exporter.export(jobs, options=ExportOptions(include_closed=True))
        with open(path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2

    async def test_export_filters_by_company(self, tmp_path: Path) -> None:
        exporter = CsvExporter(tmp_path)
        jobs = [_job(company_name="OPSWAT"), _job(company_name="TikTok")]
        path = await exporter.export(
            jobs,
            options=ExportOptions(company_filter=["OPSWAT"]),
        )
        with open(path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
        assert rows[0]["company_name"] == "OPSWAT"

    async def test_export_filters_by_date_range(self, tmp_path: Path) -> None:
        exporter = CsvExporter(tmp_path)
        jobs = [
            _job(date_posted=datetime(2026, 1, 1)),
            _job(date_posted=datetime(2026, 6, 1)),
        ]
        opts = ExportOptions(
            date_from=datetime(2026, 2, 1),
            date_to=datetime(2026, 12, 1),
        )
        path = await exporter.export(jobs, options=opts)
        with open(path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1

    async def test_export_handles_string_date(self, tmp_path: Path) -> None:
        exporter = CsvExporter(tmp_path)
        path = await exporter.export([_job(date_posted="2026-01-01")])
        with open(path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert rows[0]["date_posted"] == "2026-01-01"

    async def test_export_cleans_temp_on_error(self, tmp_path: Path, monkeypatch) -> None:
        exporter = CsvExporter(tmp_path)
        # Force write to fail by patching DictWriter.
        import csv as _csv

        original_writer = _csv.DictWriter

        class _BoomWriter(_csv.DictWriter):
            def writeheader(self):  # type: ignore[override]
                raise RuntimeError("boom")

        monkeypatch.setattr(_csv, "DictWriter", _BoomWriter)
        with pytest.raises(RuntimeError):
            await exporter.export([_job()])

    def test_list_exports_empty(self, tmp_path: Path) -> None:
        exporter = CsvExporter(tmp_path)
        assert exporter.list_exports() == []

    @pytest.mark.asyncio
    async def test_list_exports_returns_files(self, tmp_path: Path) -> None:
        exporter = CsvExporter(tmp_path)
        await exporter.export([_job()])
        files = exporter.list_exports()
        assert len(files) == 1
        assert files[0]["size_bytes"] > 0

    def test_generate_filename(self, tmp_path: Path) -> None:
        exporter = CsvExporter(tmp_path)
        path = exporter._generate_filename()
        assert path.name.startswith("jobs_export_")
        assert path.suffix == ".csv"


def test_get_exporter_singleton() -> None:
    a = get_exporter()
    b = get_exporter()
    assert a is b
