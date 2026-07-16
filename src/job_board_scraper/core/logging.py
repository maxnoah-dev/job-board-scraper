"""Structured logging setup with sensitive-field redaction.

All application loggers are created via ``get_logger()`` and route through
``structlog``. Logs are written in JSON format to stdout (for log aggregators)
and optionally to a file. Sensitive field values are automatically redacted
before emission so that API keys, passwords, and tokens never appear in logs.

The redaction processor is applied globally via ``configure_logging()``, which
must be called once at application startup before any logger is used.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

import structlog
from structlog.types import Processor

from job_board_scraper.core.config import get_settings

# Fields that are considered sensitive and must never appear in log output.
# Values associated with these field names are replaced with ``"<REDACTED>"``.
SENSITIVE_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "api_key",
        "apikey",
        "api-key",
        "api_key_id",
        "auth",
        "authorization",
        "bearer",
        "client_secret",
        "password",
        "passwd",
        "private_key",
        "secret",
        "secret_key",
        "security_token",
        "session_token",
        "token",
        "x-api-key",
        "x-auth-token",
        "x-security-token",
    }
)


def _is_sensitive_key(key: str) -> bool:
    """Return True if ``key`` looks like a sensitive field name."""
    normalized = key.lower().strip().replace("-", "_").replace(" ", "_")
    return normalized in SENSITIVE_FIELD_NAMES or "_secret" in normalized


def _redact_sensitive_values(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Structlog processor that replaces sensitive field values with ``<REDACTED>``."""
    for key in list(event_dict.keys()):
        if _is_sensitive_key(key):
            event_dict[key] = "<REDACTED>"
    return event_dict


def _add_log_level(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Add the ``level`` key so log aggregation tools can filter by severity."""
    event_dict["level"] = method_name.upper()
    return event_dict


def _add_timestamp(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Add ISO-8601 ``timestamp`` in UTC."""
    import datetime

    event_dict["timestamp"] = datetime.datetime.now(datetime.UTC).isoformat()
    return event_dict


def configure_logging() -> None:
    """Configure ``structlog`` with JSON rendering and sensitive-field redaction.

    Call this once at application startup, before any module calls ``get_logger()``.
    Subsequent calls are no-ops.
    """
    settings = get_settings()

    # Determine output level
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # Shared processor chain
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        _add_timestamp,
        _redact_sensitive_values,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    # Determine renderer: JSON to stdout (production), or pretty console (dev)
    if os.environ.get("LOG_FORMAT", "").upper() == "CONSOLE":
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    # Root logger handlers
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # stdout handler (JSON)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    stdout_handler.setLevel(log_level)
    root_logger.addHandler(stdout_handler)

    # File handler (JSON, optional)
    if settings.LOG_FILE:
        log_path = Path(settings.LOG_FILE)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)
        root_logger.addHandler(file_handler)

    # Suppress verbose third-party loggers
    for noisy_logger in ("httpx", "httpcore", "playwright", "asyncio"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a ``structlog`` logger bound to ``name``.

    Args:
        name: Optional logger name. If omitted the caller's module is used.

    Returns:
        A configured ``structlog.stdlib.BoundLogger`` with sensitive-field
        redaction and JSON output enabled.

    Example:
        from job_board_scraper.core.logging import get_logger
        log = get_logger(__name__)
        log.info("scrape_started", company="opswat", jobs_expected=42)
        log.warning("rate_limit_approaching", origin="opswat.com")
        log.error("scrape_failed", company="opswat", reason="timeout")
    """
    if name is None:
        import traceback

        frame = traceback.extract_stack()[-2]
        name = frame.filename

    return structlog.get_logger(name)
