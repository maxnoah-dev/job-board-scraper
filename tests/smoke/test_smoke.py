"""Smoke tests for the job-board-scraper application.

These tests verify the most critical application entry points without
touching the network or the database. They run fast and must always pass
so they are the first line of defence against broken deployments.

Marker: ``pytest -m e2e`` (process-level smoke).
"""

from __future__ import annotations

import pytest


@pytest.mark.e2e
class TestCliEntryPoint:
    """The CLI entry point must be importable and return the expected exit code."""

    def test_cli_module_importable(self) -> None:
        """``job_board_scraper.cli`` must be importable."""
        from job_board_scraper import cli  # noqa: F401

    def test_cli_main_is_callable(self) -> None:
        """``cli.main`` must be a callable."""
        from job_board_scraper.cli import main

        assert callable(main)

    def test_cli_main_raises_not_implemented(self) -> None:
        """``cli.main`` must raise ``SystemExit`` when called without arguments."""
        from job_board_scraper.cli import main

        with pytest.raises(SystemExit) as exc_info:
            main()
        # argparse exits with code 2 when required subcommand is missing
        assert exc_info.value.code == 2


@pytest.mark.e2e
class TestCoreModules:
    """Core modules must be importable and expose their public API."""

    def test_settings_singleton(self) -> None:
        """``get_settings()`` must return an ``AppSettings`` instance."""
        from job_board_scraper.core.config import get_settings

        settings = get_settings()
        assert settings is not None
        assert hasattr(settings, "DATABASE_URL")
        assert hasattr(settings, "LOG_LEVEL")

    def test_logging_configured(self) -> None:
        """``get_logger()`` must return a structlog logger."""
        from job_board_scraper.core.logging import get_logger

        logger = get_logger()
        assert logger is not None
        assert callable(logger.info)
        assert callable(logger.warning)
        assert callable(logger.error)


@pytest.mark.e2e
class TestPackageStructure:
    """Package structure must match TECHNICAL.md §4."""

    def test_root_package_version(self) -> None:
        """``job_board_scraper.__version__`` must be a non-empty string."""
        import job_board_scraper

        assert hasattr(job_board_scraper, "__version__")
        assert isinstance(job_board_scraper.__version__, str)
        assert len(job_board_scraper.__version__) > 0

    def test_adapter_registry_exists(self) -> None:
        """``job_board_scraper.adapters.registry`` must be importable."""
        from job_board_scraper.adapters import registry  # noqa: F401

    def test_etl_base_exists(self) -> None:
        """``job_board_scraper.etl.base`` must be importable."""
        from job_board_scraper.etl import base  # noqa: F401

    def test_monitoring_alert_manager_exists(self) -> None:
        """``job_board_scraper.monitoring.alert_manager`` must be importable."""
        from job_board_scraper.monitoring import alert_manager  # noqa: F401

    def test_scheduler_exists(self) -> None:
        """``job_board_scraper.scheduler.scheduler`` must be importable."""
        from job_board_scraper.scheduler import scheduler  # noqa: F401

    def test_utils_retry_exists(self) -> None:
        """``job_board_scraper.utils.retry`` must be importable."""
        from job_board_scraper.utils import retry  # noqa: F401

    def test_opswat_adapter_stub_exists(self) -> None:
        """The OPSWAT adapter stub must exist for Phase 4."""
        from job_board_scraper.adapters.implementations import (
            opswat_adapter,  # noqa: F401
        )
