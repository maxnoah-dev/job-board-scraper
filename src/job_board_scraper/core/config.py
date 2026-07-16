"""Pydantic-powered settings with environment variable precedence.

All secrets and deployment-specific values come from environment variables.
``.env.example`` documents the full schema with placeholder values that are
safe to commit. No real secrets ever appear in source control.

Fields are grouped by concern (Database, Scheduler, Alerting, Rate Limiting,
Browser). The ``AppSettings`` class is the single Pydantic settings root
used throughout the application.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Application-wide settings loaded from environment variables.

    ``DATABASE_URL`` and ``LOG_LEVEL`` are the only fields that default
    to safe values; every other field is required and must be set by the
    operator before the pipeline starts.

    Raises:
        ValidationError: when a required field is absent and has no default.

    Example:
        from job_board_scraper.core.config import get_settings
        settings = get_settings()
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        env_nested_delimiter="_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ─── Database ────────────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./data/jobs.db",
        description="Async database DSN. SQLite default is for local dev only.",
    )

    # ─── Scheduler ──────────────────────────────────────────────────────────
    SCHEDULE_CRON: str = Field(
        default="0 2 * * *",
        description="Cron expression for the scheduled scrape. Used by APScheduler "
        "wrapper; external schedulers read this as documentation.",
    )
    TIMEZONE: str = Field(
        default="UTC",
        description="Timezone for schedule interpretation. Always UTC in production.",
    )
    SCHEDULER_ENABLED: bool = Field(
        default=False,
        description="Enable the APScheduler wrapper. Disable in production "
        "(use external scheduler instead per ADR-0006).",
    )
    RUN_TIMEOUT_SECONDS: int = Field(
        default=3600,
        description="Maximum duration in seconds for a single ETL run. "
        "Runs that exceed this are marked `interrupted`.",
    )

    # ─── Alerting ─────────────────────────────────────────────────────────
    ALERT_EMAIL_ENABLED: bool = Field(
        default=False,
        description="Enable email alerting sink.",
    )
    ALERT_EMAIL_TO: str = Field(
        default="",
        description="Comma-separated list of recipient email addresses.",
    )
    ALERT_EMAIL_FROM: str = Field(
        default="",
        description="Sender email address.",
    )
    ALERT_EMAIL_SMTP_HOST: str = Field(
        default="localhost",
        description="SMTP server hostname.",
    )
    ALERT_EMAIL_SMTP_PORT: int = Field(
        default=587,
        description="SMTP server port.",
    )
    ALERT_SLACK_WEBHOOK: str = Field(
        default="",
        description="Slack incoming webhook URL. Leave empty to disable Slack alerting.",
    )

    # ─── Logging ───────────────────────────────────────────────────────────
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Minimum log level. Accepted values: DEBUG, INFO, WARNING, ERROR.",
    )
    LOG_FILE: str = Field(
        default="./logs/scraper.log",
        description="Path to the log file. Set to empty string to disable file logging.",
    )

    # ─── Rate Limiting ─────────────────────────────────────────────────────
    REQUEST_DELAY_MIN: int = Field(
        default=2,
        description="Minimum delay in seconds between consecutive requests to "
        "the same origin.",
    )
    REQUEST_DELAY_MAX: int = Field(
        default=5,
        description="Maximum delay in seconds between consecutive requests.",
    )
    MAX_CONCURRENT_ADAPTERS: int = Field(
        default=5,
        description="Maximum number of adapters that may run concurrently.",
    )

    # ─── Browser Automation ────────────────────────────────────────────────
    BROWSER_HEADLESS: bool = Field(
        default=True,
        description="Run browser in headless mode. Set False for debugging.",
    )
    BROWSER_TIMEOUT_MS: int = Field(
        default=30000,
        description="Browser page load timeout in milliseconds.",
    )
    PLAYWRIGHT_BROWSERS_INSTALLED: bool = Field(
        default=False,
        description="Set True if Playwright browsers are installed. "
        "Enabling browser adapters without this causes startup failure.",
    )

    # ─── Export ────────────────────────────────────────────────────────────
    EXPORT_DIR: str = Field(
        default="./data",
        description="Directory where CSV export files are written.",
    )
    EXPORT_DEFAULT_OPEN_JOBS_ONLY: bool = Field(
        default=True,
        description="When True, CSV export contains only open jobs. "
        "Set False to include closed job history.",
    )

    def model_post_init(self, _warnings: object) -> None:  # type: ignore[override]
        # Validate LOG_LEVEL
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.LOG_LEVEL.upper() not in valid_levels:
            raise ValueError(
                f"LOG_LEVEL={self.LOG_LEVEL!r} not in {valid_levels}"
            )

        # Validate DELAY_MIN <= DELAY_MAX
        if self.REQUEST_DELAY_MIN > self.REQUEST_DELAY_MAX:
            raise ValueError(
                f"REQUEST_DELAY_MIN ({self.REQUEST_DELAY_MIN}) must not exceed "
                f"REQUEST_DELAY_MAX ({self.REQUEST_DELAY_MAX})"
            )

        # Ensure export directory exists
        if self.EXPORT_DIR:
            Path(self.EXPORT_DIR).mkdir(parents=True, exist_ok=True)

        # Ensure log directory exists
        if self.LOG_FILE:
            log_path = Path(self.LOG_FILE)
            log_path.parent.mkdir(parents=True, exist_ok=True)


_settings: AppSettings | None = None


def get_settings() -> AppSettings:
    """Return the cached ``AppSettings`` singleton.

    Settings are loaded once on first call and reused for the lifetime of
    the process. This matches the pydantic-settings recommended pattern.
    """
    global _settings
    if _settings is None:
        _settings = AppSettings()
    return _settings
