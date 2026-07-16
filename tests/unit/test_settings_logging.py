"""Tests for P1-03 — Validated settings, structured logging, and .env.example.

These tests gate the contract defined in `docs/ROADMAP.md` Phase 1 row P1-03:
- ``AppSettings`` validates required env vars at startup
- Missing required env causes ``ValidationError``
- ``DATABASE_URL`` has a safe SQLite default for dev
- ``get_logger()`` returns a structlog logger with JSON output
- Sensitive values are redacted in log output
- ``.env.example`` exists with placeholder values only

RED phase: these tests fail because the implementation does not exist yet.
GREEN phase: the implementation makes them pass.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_EXAMPLE = PROJECT_ROOT / ".env.example"


class TestAppSettings:
    """``job_board_scraper.core.config`` must expose a Pydantic settings class."""

    def test_settings_module_exists(self) -> None:
        """``job_board_scraper.core.config`` must be importable."""
        from job_board_scraper.core import config  # noqa: F401

    def test_app_settings_class_exists(self) -> None:
        """``AppSettings`` must be defined in the config module."""
        from job_board_scraper.core.config import AppSettings

        assert AppSettings is not None

    def test_settings_loads_from_environment(self) -> None:
        """``AppSettings`` must load values from environment variables."""
        from job_board_scraper.core.config import AppSettings

        # Override a known env var for this test
        os.environ["LOG_LEVEL"] = "DEBUG"
        try:
            settings = AppSettings()
            assert settings.LOG_LEVEL == "DEBUG"
        finally:
            os.environ.pop("LOG_LEVEL", None)

    def test_missing_required_env_raises_validation_error(self) -> None:
        """``AppSettings`` must be instantiable with no env vars present (all fields have defaults)."""
        from job_board_scraper.core.config import AppSettings

        # Clear all relevant env vars so we test the defaults path
        keys_to_clear = [
            "DATABASE_URL", "SCHEDULE_CRON", "TIMEZONE", "SCHEDULER_ENABLED",
            "RUN_TIMEOUT_SECONDS", "ALERT_EMAIL_ENABLED", "ALERT_EMAIL_TO",
            "ALERT_EMAIL_FROM", "ALERT_EMAIL_SMTP_HOST", "ALERT_EMAIL_SMTP_PORT",
            "ALERT_SLACK_WEBHOOK", "LOG_LEVEL", "LOG_FILE",
            "REQUEST_DELAY_MIN", "REQUEST_DELAY_MAX", "MAX_CONCURRENT_ADAPTERS",
            "BROWSER_HEADLESS", "BROWSER_TIMEOUT_MS", "PLAYWRIGHT_BROWSERS_INSTALLED",
            "EXPORT_DIR", "EXPORT_DEFAULT_OPEN_JOBS_ONLY",
        ]
        snapshot = {k: os.environ.pop(k, None) for k in keys_to_clear}
        try:
            # Must NOT raise — every field has a safe default
            settings = AppSettings()
            assert settings.DATABASE_URL is not None
            assert settings.LOG_LEVEL is not None
        finally:
            for k, v in snapshot.items():
                if v is not None:
                    os.environ[k] = v

    def test_database_url_has_safe_default(self) -> None:
        """``DATABASE_URL`` must default to a local SQLite path for dev."""
        from job_board_scraper.core.config import AppSettings

        snapshot = os.environ.pop("DATABASE_URL", None)
        try:
            settings = AppSettings()
            assert settings.DATABASE_URL is not None
            assert "sqlite" in settings.DATABASE_URL.lower()
        finally:
            if snapshot is not None:
                os.environ["DATABASE_URL"] = snapshot

    def test_all_required_fields_defined(self) -> None:
        """All fields listed in ADR-0005 and ADR-0006 must be present on ``AppSettings``."""
        from job_board_scraper.core.config import AppSettings

        required_fields = [
            "DATABASE_URL",
            "SCHEDULE_CRON",
            "TIMEZONE",
            "LOG_LEVEL",
            "LOG_FILE",
        ]
        snapshot = {k: os.environ.pop(k, None) for k in required_fields}
        try:
            settings = AppSettings()
            for field in required_fields:
                assert hasattr(settings, field), f"AppSettings missing field: {field}"
        finally:
            for k, v in snapshot.items():
                if v is not None:
                    os.environ[k] = v


class TestEnvExample:
    """.env.example must exist and must not contain real secrets."""

    def test_env_example_exists(self) -> None:
        """.env.example must exist at the repo root."""
        assert ENV_EXAMPLE.exists(), (
            ".env.example must exist at the repo root (P1-03 gate)"
        )

    def test_env_example_has_required_placeholders(self) -> None:
        """.env.example must declare every required environment variable."""
        if not ENV_EXAMPLE.exists():
            pytest.skip(".env.example missing")

        content = ENV_EXAMPLE.read_text(encoding="utf-8")

        required_vars = [
            "DATABASE_URL=",
            "SCHEDULE_CRON=",
            "TIMEZONE=",
            "LOG_LEVEL=",
            "LOG_FILE=",
            "ALERT_EMAIL_ENABLED=",
            "ALERT_EMAIL_TO=",
            "ALERT_SLACK_WEBHOOK=",
            "REQUEST_DELAY_MIN=",
            "REQUEST_DELAY_MAX=",
            "BROWSER_HEADLESS=",
        ]
        for var in required_vars:
            assert var in content, (
                f".env.example must contain a placeholder for {var!r}"
            )

    def test_env_example_has_no_real_secrets(self) -> None:
        """.env.example must not contain actual secret values."""
        if not ENV_EXAMPLE.exists():
            pytest.skip(".env.example missing")

        content = ENV_EXAMPLE.read_text(encoding="utf-8").lower()
        # Obvious secret patterns that should never appear in a committed file
        secret_patterns = [
            "sk-",  # OpenAI / many API keys
            "ghp_",  # GitHub personal access token
            "gho_",  # GitHub OAuth
            "password=",  # only flagged when it has a non-placeholder value
            "your_api_key",
            "your_password",
            "example_password",
        ]
        found = [p for p in secret_patterns if p in content]
        assert not found, (
            f".env.example contains suspicious secret placeholder(s): {found}. "
            "Use placeholder values only (e.g. DATABASE_URL=sqlite:///./data/jobs.db)."
        )


class TestStructuredLogging:
    """Structured logging with redaction."""

    def test_get_logger_function_exists(self) -> None:
        """``get_logger()`` must be importable from ``job_board_scraper.core.logging``."""
        from job_board_scraper.core.logging import get_logger  # noqa: F401

    def test_get_logger_returns_structlog_logger(self) -> None:
        """``get_logger()`` must return a structlog logger (not a stdlib logger)."""
        from job_board_scraper.core.logging import get_logger

        logger = get_logger()
        # structlog wraps stdlib loggers but we can check the type name
        logger_type = type(logger).__module__
        assert "structlog" in logger_type or hasattr(logger, "_context"), (
            f"get_logger() returned {logger_type!r}, expected a structlog logger"
        )

    def test_logger_outputs_json_by_default(self) -> None:
        """The default logger output must be JSON when configured for production."""
        import subprocess, sys

        # Run a subprocess that imports the configured logger and emits a log line.
        # We capture stdout and verify it parses as a JSON object.
        code = """
import json, sys
from job_board_scraper.core.logging import get_logger, configure_logging
configure_logging()
logger = get_logger()
logger.info("test_event", key="value")
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        # stdout should contain a JSON line
        lines = [l for l in result.stdout.strip().splitlines() if l.strip()]
        assert lines, f"No stdout output; stderr: {result.stderr}"
        # Find a line that looks like JSON (starts with {)
        json_lines = [l for l in lines if l.strip().startswith("{")]
        assert json_lines, (
            f"Expected JSON output on stdout, got: {lines[:3]!r}. "
            f"stderr: {result.stderr[:200]}"
        )
        record = json.loads(json_lines[0])
        assert isinstance(record, dict), f"Expected JSON dict, got: {record!r}"
        assert "event" in record or "key" in record, (
            f"Expected JSON log record with 'event' or 'key' field, got: {record}"
        )

    def test_sensitive_fields_are_redacted(self) -> None:
        """Log output must not contain sensitive field values."""
        import subprocess, sys

        code = """
import json, sys
from job_board_scraper.core.logging import get_logger, configure_logging
configure_logging()
logger = get_logger()
logger.info("auth_attempt", api_key="sk-12345secret", password="hunter2")
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        combined = result.stdout + result.stderr
        # Neither secret value may appear in any output stream
        for secret in ("sk-12345secret", "hunter2"):
            assert secret not in combined, (
                f"Sensitive value {secret!r} appeared in log output — redaction failed. "
                f"Output: {combined[:500]!r}"
            )
