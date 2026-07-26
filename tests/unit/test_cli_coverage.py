"""Unit tests for ``cli.py`` covering all subcommands and the parser.

These tests stub out the heavy modules (database, scripts) so we can exercise
every code path without touching real SQLite or scripts.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from job_board_scraper import cli as cli_module
from job_board_scraper.etl.pipeline import PipelineExitCode


def _args(**kwargs: object) -> argparse.Namespace:
    """Build a synthetic argparse.Namespace for a given subcommand."""
    base: dict[str, object] = {
        "verbose": False,
        "command": "run",
        "company": None,
        "dry_run": False,
        "with_vilao": False,
        "force": False,
        "output": None,
        "open_only": True,
        "include_closed": False,
        "template": None,
        "sheet_name": "From Scraper",
    }
    base.update(kwargs)
    return argparse.Namespace(**base)


def _run_in_fresh_loop(coro_factory):
    """Run an async coroutine factory in a fresh asyncio loop.

    pytest-asyncio keeps the default loop running in test threads, which
    prevents ``asyncio.run`` from creating a new loop. This helper creates
    an isolated loop for the duration of one call.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro_factory())
    finally:
        loop.close()


class TestSetupLogging:
    def test_setup_logging_runs_without_verbose(self) -> None:
        # setup_logging(configures handlers on root logger; no exception is enough).
        cli_module.setup_logging(verbose=False)

    def test_setup_logging_runs_with_verbose(self) -> None:
        cli_module.setup_logging(verbose=True)


class TestPrintSummary:
    def _result(self, **kw: object):
        from datetime import datetime

        from job_board_scraper.etl.pipeline import PipelineResult

        defaults: dict[str, object] = {
            "run_id": 1,
            "status": PipelineExitCode.SUCCESS,
            "started_at": datetime(2026, 1, 1, 0, 0, 0),
            "finished_at": datetime(2026, 1, 1, 0, 0, 12),
            "total_jobs_found": 10,
            "total_new_jobs": 5,
            "total_closed_jobs": 1,
            "total_errors": 0,
            "company_results": [],
        }
        defaults.update(kw)
        return PipelineResult(**defaults)  # type: ignore[arg-type]

    def test_print_summary_short(self, capsys) -> None:
        cli_module._print_summary(self._result(), verbose=False)
        captured = capsys.readouterr()
        assert "SCRAPE SUMMARY" in captured.out
        assert "Total Jobs: 10" in captured.out
        assert "All companies scraped successfully." in captured.out

    def test_print_summary_verbose(self, capsys) -> None:
        from job_board_scraper.etl.pipeline import ScrapeResult

        cr = ScrapeResult(
            company_id=1,
            company_slug="opswat",
            status=PipelineExitCode.PARTIAL,
            jobs_found=3,
            new_jobs=2,
            closed_jobs=1,
            duration_ms=200,
            error_type=None,
            error_message=None,
        )
        result = self._result(
            status=PipelineExitCode.PARTIAL,
            company_results=[cr],
        )
        cli_module._print_summary(result, verbose=True)
        out = capsys.readouterr().out
        assert "opswat" in out
        assert "PER-COMPANY RESULTS" in out

    def test_print_summary_failure(self, capsys) -> None:
        cli_module._print_summary(self._result(status=PipelineExitCode.FAILED))
        out = capsys.readouterr().out
        assert "SCRAPE FAILED" in out


class TestCmdRun:
    @pytest.mark.asyncio
    async def test_cmd_run_returns_success(self) -> None:
        from datetime import datetime

        from job_board_scraper.etl.pipeline import PipelineResult

        pipeline_result = PipelineResult(
            run_id=1,
            status=PipelineExitCode.SUCCESS,
            started_at=datetime(2026, 1, 1),
            finished_at=datetime(2026, 1, 1, 0, 0, 1),
            total_jobs_found=0,
            total_new_jobs=0,
            total_closed_jobs=0,
            total_errors=0,
            company_results=[],
        )

        pipeline = MagicMock()
        pipeline.run = AsyncMock(return_value=pipeline_result)

        args = _args(command="run", company="opswat", dry_run=True, with_vilao=False)
        with (
            patch.object(cli_module, "init_db", new=AsyncMock()),
            patch.object(cli_module, "check_connection", new=AsyncMock(return_value=True)),
            patch.object(cli_module, "close_db", new=AsyncMock()),
            patch.object(cli_module, "create_pipeline", return_value=pipeline),
        ):
            rc = await cli_module.cmd_run(args)
        assert rc == PipelineExitCode.SUCCESS.value

    @pytest.mark.asyncio
    async def test_cmd_run_returns_failed_when_no_db(self) -> None:
        args = _args(command="run", dry_run=False)
        with (
            patch.object(cli_module, "init_db", new=AsyncMock()),
            patch.object(
                cli_module, "check_connection", new=AsyncMock(return_value=False)
            ),
            patch.object(cli_module, "close_db", new=AsyncMock()),
        ):
            rc = await cli_module.cmd_run(args)
        assert rc == PipelineExitCode.FAILED.value

    @pytest.mark.asyncio
    async def test_cmd_run_catches_keyboard_interrupt(self) -> None:
        pipeline = MagicMock()
        pipeline.run = AsyncMock(side_effect=KeyboardInterrupt())
        args = _args(command="run", dry_run=False, with_vilao=False)

        with (
            patch.object(cli_module, "init_db", new=AsyncMock()),
            patch.object(cli_module, "check_connection", new=AsyncMock(return_value=True)),
            patch.object(cli_module, "close_db", new=AsyncMock()),
            patch.object(cli_module, "create_pipeline", return_value=pipeline),
        ):
            rc = await cli_module.cmd_run(args)
        assert rc == PipelineExitCode.FAILED.value

    @pytest.mark.asyncio
    async def test_cmd_run_catches_generic_exception(self) -> None:
        pipeline = MagicMock()
        pipeline.run = AsyncMock(side_effect=RuntimeError("boom"))
        args = _args(command="run", dry_run=False, with_vilao=False)

        with (
            patch.object(cli_module, "init_db", new=AsyncMock()),
            patch.object(cli_module, "check_connection", new=AsyncMock(return_value=True)),
            patch.object(cli_module, "close_db", new=AsyncMock()),
            patch.object(cli_module, "create_pipeline", return_value=pipeline),
        ):
            rc = await cli_module.cmd_run(args)
        assert rc == PipelineExitCode.FAILED.value


class TestCmdInitDbAndSeed:
    def test_cmd_init_db_invokes_script(self) -> None:
        import scripts.init_db
        import scripts.seed_companies  # noqa: F401 ensure parent package loaded

        with patch.object(scripts.init_db, "main", return_value=0):
            assert cli_module.cmd_init_db(_args()) == 0

    def test_cmd_seed_invokes_script(self) -> None:
        import scripts.seed_companies

        with patch.object(scripts.seed_companies, "main", return_value=0):
            assert cli_module.cmd_seed(_args(force=False)) == 0
            assert cli_module.cmd_seed(_args(force=True)) == 0


class TestCmdExport:
    def test_cmd_export_fails_when_db_unreachable(self) -> None:
        with (
            patch(
                "job_board_scraper.core.database.check_connection",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "job_board_scraper.core.database.close_db", new=AsyncMock()
            ),
        ):
            rc = cli_module.cmd_export(
                _args(command="export", output="x.csv", open_only=True)
            )
        assert rc == 1

    def test_cmd_export_calls_exporter(self, tmp_path) -> None:
        exporter = MagicMock()
        exporter.export = AsyncMock(return_value=7)
        exporter.output_path = tmp_path / "jobs.csv"

        with (
            patch(
                "job_board_scraper.core.database.check_connection",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "job_board_scraper.core.database.close_db", new=AsyncMock()
            ),
            patch(
                "job_board_scraper.reporting.csv_exporter.CsvExporter",
                return_value=exporter,
            ),
        ):
            rc = cli_module.cmd_export(
                _args(command="export", output="jobs.csv", open_only=False)
            )
        assert rc == 0
        assert exporter.export.await_count == 1


class TestMain:
    def test_main_run_subcommand(self) -> None:
        with (
            patch.object(sys, "argv", ["job-board-scraper", "run", "-c", "opswat", "--dry-run"]),
            patch.object(
                cli_module,
                "cmd_run",
                new=AsyncMock(return_value=0),
            ),
            patch.object(cli_module, "setup_logging"),
        ):
            assert cli_module.main() == 0

    def test_main_unknown_subcommand(self, capsys) -> None:
        # Patch subparsers to require command, so simulate with a known command + invalid arg
        with (
            patch.object(sys, "argv", ["job-board-scraper", "init-db"]),
            patch.object(cli_module, "setup_logging"),
            patch.object(cli_module, "cmd_init_db", return_value=0),
        ):
            assert cli_module.main() == 0

    def test_main_seed_with_force(self) -> None:
        with (
            patch.object(sys, "argv", ["job-board-scraper", "seed", "--force"]),
            patch.object(cli_module, "setup_logging"),
            patch.object(cli_module, "cmd_seed", return_value=0),
        ):
            assert cli_module.main() == 0

    def test_main_export_xlsx(self) -> None:
        with (
            patch.object(
                sys, "argv", ["job-board-scraper", "export-xlsx", "-o", "out.xlsx"]
            ),
            patch.object(cli_module, "setup_logging"),
            patch.object(cli_module, "cmd_export_xlsx", return_value=0),
        ):
            assert cli_module.main() == 0

    def test_main_export(self) -> None:
        with (
            patch.object(sys, "argv", ["job-board-scraper", "export", "-o", "o.csv"]),
            patch.object(cli_module, "setup_logging"),
            patch.object(cli_module, "cmd_export", return_value=0),
        ):
            assert cli_module.main() == 0


class TestCmdExportXlsxIntegration:
    def _session_rows(self):
        # returns (Job, Company)
        job = MagicMock()
        job.title = "Senior Engineer"
        job.title_vi = "Kỹ sư cao cấp"
        job.url = "https://example.com/jobs/1"
        job.location = "Remote"
        job.status = "open"
        job.salary_raw = "$200K/yr"
        job.raw_data = {}
        company = MagicMock()
        company.name = "OPSWAT"
        company.slug = "opswat"
        return [(job, company)]

    def test_cmd_export_xlsx_fails_when_db_unreachable(self) -> None:
        with (
            patch(
                "job_board_scraper.core.database.check_connection",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "job_board_scraper.core.database.close_db", new=AsyncMock()
            ),
            patch("job_board_scraper.core.config.get_settings") as settings_mock,
        ):
            settings_mock.return_value.EXPORT_DIR = Path("/tmp")
            args = _args(command="export-xlsx", output=None, template=None)
            rc = cli_module.cmd_export_xlsx(args)
        assert rc == 1

    def test_cmd_export_xlsx_writes_workbook(self, tmp_path, monkeypatch) -> None:
        output_path = tmp_path / "out.xlsx"
        template_path = tmp_path / "template.xlsx"

        class _SessionCtx:
            async def __aenter__(self):
                session = MagicMock()
                session.execute = AsyncMock(
                    return_value=MagicMock(all=MagicMock(return_value=[]))
                )
                return session

            async def __aexit__(self, *a):
                return False

        exporter = MagicMock()
        exporter.export = AsyncMock(return_value=output_path)

        with (
            patch(
                "job_board_scraper.core.database.check_connection",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "job_board_scraper.core.database.close_db", new=AsyncMock()
            ),
            patch("job_board_scraper.core.config.get_settings") as settings_mock,
            patch(
                "job_board_scraper.core.database.session_scope",
                new=lambda: _SessionCtx(),
            ),
            patch(
                "job_board_scraper.reporting.excel_exporter.ExcelExporter",
                return_value=exporter,
            ),
        ):
            settings_mock.return_value.EXPORT_DIR = tmp_path
            args = _args(
                command="export-xlsx",
                output=str(output_path),
                template=str(template_path),
                sheet_name="From Scraper",
                include_closed=True,
            )
            rc = cli_module.cmd_export_xlsx(args)
        assert rc == 0
