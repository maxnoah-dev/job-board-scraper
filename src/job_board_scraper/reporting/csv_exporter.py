"""Reporting module for export functionality.

Provides deterministic atomic CSV export of job data.
"""

from __future__ import annotations

import csv
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass
class ExportOptions:
    """Options for job export."""

    include_closed: bool = False
    company_filter: list[str] | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    output_path: Path | None = None


class CsvExporter:
    """Exports jobs to CSV format with atomic writes."""

    # Standard columns for CSV export
    COLUMNS = [
        "company_name",
        "job_title",
        "location",
        "job_url",
        "date_posted",
        "status",
        "canonical_url",
    ]

    def __init__(self, output_dir: Path | str = "./data/exports") -> None:
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def _generate_filename(self, prefix: str = "jobs_export") -> Path:
        """Generate a unique filename with timestamp."""
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        return self._output_dir / f"{prefix}_{timestamp}.csv"

    def _validate_job(self, job: dict, options: ExportOptions) -> bool:
        """Validate if a job should be included based on options."""
        # Filter by company
        if options.company_filter:
            company = job.get("company_name", "")
            if company not in options.company_filter:
                return False

        # Filter by status
        if not options.include_closed:
            status = job.get("status", "open")
            if status == "closed":
                return False

        # Filter by date range
        date_posted = job.get("date_posted")
        if date_posted:
            if options.date_from and date_posted < options.date_from:
                return False
            if options.date_to and date_posted > options.date_to:
                return False

        return True

    async def export(
        self,
        jobs: list[dict],
        options: ExportOptions | None = None,
    ) -> Path:
        """Export jobs to CSV with atomic write.

        Uses a temporary file and rename for atomicity.
        """
        options = options or ExportOptions()
        output_path = options.output_path or self._generate_filename()

        # Write to temporary file first
        fd, temp_path = tempfile.mkstemp(suffix=".csv", dir=str(self._output_dir))
        os.close(fd)

        try:
            with open(temp_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.COLUMNS)
                writer.writeheader()

                for job in jobs:
                    if self._validate_job(job, options):
                        row = {
                            "company_name": job.get("company_name", ""),
                            "job_title": job.get("title", ""),
                            "location": job.get("location", ""),
                            "job_url": job.get("job_url", ""),
                            "date_posted": (
                                job.get("date_posted", "").isoformat()
                                if hasattr(job.get("date_posted", ""), "isoformat")
                                else str(job.get("date_posted", ""))
                            ),
                            "status": job.get("status", "open"),
                            "canonical_url": job.get("canonical_url", ""),
                        }
                        writer.writerow(row)

            # Atomic rename
            os.replace(temp_path, output_path)
            return output_path

        except Exception:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    def list_exports(self) -> list[dict]:
        """List all export files in the output directory."""
        exports = []
        if not self._output_dir.exists():
            return exports

        for path in sorted(self._output_dir.glob("jobs_export_*.csv")):
            stat = path.stat()
            exports.append(
                {
                    "filename": path.name,
                    "path": str(path),
                    "size_bytes": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_ctime, tz=UTC),
                    "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                }
            )

        return exports


# Global exporter instance
_exporter: CsvExporter | None = None


def get_exporter() -> CsvExporter:
    """Get or create the global CSV exporter."""
    global _exporter
    if _exporter is None:
        _exporter = CsvExporter()
    return _exporter
