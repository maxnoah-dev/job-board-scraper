"""Tests for P9 scripts: init_db.py and seed_companies.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class TestInitDbScript:
    """init-db CLI subcommand smoke tests."""

    def test_init_db_module_importable(self) -> None:
        """The init_db module must be importable."""
        src = PROJECT_ROOT / "src"
        if str(src) not in sys.path:
            sys.path.insert(0, str(src))
        import scripts.init_db  # noqa: F401

        assert hasattr(scripts.init_db, "main")
        assert callable(scripts.init_db.main)

    def test_init_db_main_is_callable(self) -> None:
        src = PROJECT_ROOT / "src"
        if str(src) not in sys.path:
            sys.path.insert(0, str(src))
        import scripts.init_db

        assert callable(scripts.init_db.main)


class TestSeedCompaniesScript:
    """seed-companies CLI subcommand smoke tests."""

    def test_seed_companies_module_importable(self) -> None:
        src = PROJECT_ROOT / "src"
        if str(src) not in sys.path:
            sys.path.insert(0, str(src))
        import scripts.seed_companies  # noqa: F401

        assert hasattr(scripts.seed_companies, "main")
        assert callable(scripts.seed_companies.main)

    def test_seed_companies_main_is_callable(self) -> None:
        src = PROJECT_ROOT / "src"
        if str(src) not in sys.path:
            sys.path.insert(0, str(src))
        import scripts.seed_companies

        assert callable(scripts.seed_companies.main)

    def test_seed_companies_has_expected_slugs(self) -> None:
        """Seed data must contain the approved + needs-review companies."""
        src = PROJECT_ROOT / "src"
        if str(src) not in sys.path:
            sys.path.insert(0, str(src))
        import scripts.seed_companies

        slugs = {c["slug"] for c in scripts.seed_companies._SEED_COMPANIES}
        assert "opswat" in slugs
        assert "vancity" in slugs
        assert "techcorp" in slugs

    def test_seed_companies_skips_blocked(self) -> None:
        """Browser/blocked sources must not be active."""
        src = PROJECT_ROOT / "src"
        if str(src) not in sys.path:
            sys.path.insert(0, str(src))
        import scripts.seed_companies

        for company in scripts.seed_companies._SEED_COMPANIES:
            if company["slug"] == "tiktok":
                assert company["is_active"] is False, (
                    "TikTok must be inactive (blocked-by-policy)"
                )
                assert company["compliance_status"] == "blocked-by-policy"
            if company["slug"] == "northrop":
                assert company["is_active"] is False, (
                    "Northrop must be inactive (blocked-by-policy)"
                )
                assert company["compliance_status"] == "blocked-by-policy"


class TestCliEntrypoint:
    """CLI entrypoint module smoke tests."""

    def test_cli_module_importable(self) -> None:
        src = PROJECT_ROOT / "src"
        if str(src) not in sys.path:
            sys.path.insert(0, str(src))
        import job_board_scraper.cli  # noqa: F401

        assert hasattr(job_board_scraper.cli, "main")
        assert callable(job_board_scraper.cli.main)

    def test_cli_main_requires_subcommand(self) -> None:
        """main() must exit non-zero when no subcommand is given."""
        src = PROJECT_ROOT / "src"
        if str(src) not in sys.path:
            sys.path.insert(0, str(src))
        import job_board_scraper.cli

        with pytest.raises(SystemExit) as exc_info:
            job_board_scraper.cli.main()
        # argparse exits with code 2 when required subcommand is missing
        assert exc_info.value.code == 2

    def test_cli_subcommand_run_recognized(self) -> None:
        """`run --help` must exit successfully, showing the run subcommand."""
        src = PROJECT_ROOT / "src"
        if str(src) not in sys.path:
            sys.path.insert(0, str(src))
        import job_board_scraper.cli

        with pytest.raises(SystemExit) as exc_info:
            # Fake argv so argparse thinks we passed "run --help"
            sys.argv = ["job-board-scraper", "run", "--help"]
            job_board_scraper.cli.main()
        # argparse exits with 0 when printing help
        assert exc_info.value.code == 0
