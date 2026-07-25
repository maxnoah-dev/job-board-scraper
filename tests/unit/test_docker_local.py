"""Static contract tests for the local Docker development stack."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_runtime_copies_virtualenv_from_builder_workdir() -> None:
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "WORKDIR /app" in dockerfile
    assert (
        "COPY --from=builder --chown=scraper:scraper /app/.venv /app/.venv"
        in dockerfile
    )


def test_compose_exposes_local_database_and_dashboard() -> None:
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "POSTGRES_USER: ${POSTGRES_USER:-jobs}" in compose
    assert '"127.0.0.1:${POSTGRES_PORT:-5432}:5432"' in compose
    assert "web:" in compose
    assert '"127.0.0.1:${WEB_PORT:-8000}:8000"' in compose
    assert "job_board_scraper.web.app:app" in compose


def test_compose_initializes_data_before_starting_dashboard() -> None:
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "bootstrap:" in compose
    assert "condition: service_completed_successfully" in compose
    assert "job_board_scraper.cli init-db" in compose
    assert "job_board_scraper.cli seed" in compose


def test_pipeline_factory_registers_runnable_adapters() -> None:
    from job_board_scraper.adapters.registry import registry
    from job_board_scraper.etl.pipeline import create_pipeline

    registry.clear()
    create_pipeline()

    assert {"opswat", "vancity", "techcorp"}.issubset(registry.list_adapters())
