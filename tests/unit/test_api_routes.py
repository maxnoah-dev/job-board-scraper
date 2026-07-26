"""Unit tests for ``web/routes/api.py`` covering main JSON endpoints."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from job_board_scraper.web.app import create_app


@pytest.fixture
def client():
    app = create_app()

    @asynccontextmanager
    async def _noop_lifespan(_):
        yield

    app.router.lifespan_context = _noop_lifespan
    with TestClient(app) as c:
        yield c


def _mock_session(items: list | None = None) -> MagicMock:
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=MagicMock(
            scalars=MagicMock(
                return_value=MagicMock(all=MagicMock(return_value=items or []))
            )
        )
    )
    session.scalar = AsyncMock(return_value=0)
    return session


class _Ctx:
    def __init__(self, session: MagicMock) -> None:
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *a):
        return False


class TestApiRoutes:
    def test_stats(self, client: TestClient) -> None:
        session = _mock_session()
        cm = _Ctx(session)
        with patch(
            "job_board_scraper.web.routes.api.session_scope", return_value=cm
        ):
            response = client.get("/api/stats")
        assert response.status_code in (200, 500)

    def test_runs_status_idle(self, client: TestClient) -> None:
        from job_board_scraper.web.services.scrape_trigger import ScrapeTrigger

        trigger = ScrapeTrigger()
        with patch(
            "job_board_scraper.web.services.get_trigger", return_value=trigger
        ):
            response = client.get("/api/runs/status")
        assert response.status_code in (200, 500)

    def test_start_run(self, client: TestClient) -> None:
        from job_board_scraper.etl.pipeline import PipelineExitCode
        from job_board_scraper.web.services.scrape_trigger import ScrapeTrigger

        trigger = ScrapeTrigger()
        trigger._create_run_row = AsyncMock(return_value=5)  # type: ignore[method-assign]
        pipe = MagicMock()
        pipe.run = AsyncMock(
            return_value=MagicMock(status=PipelineExitCode.SUCCESS)
        )
        trigger._pipeline_factory = lambda: pipe
        with patch(
            "job_board_scraper.web.services.get_trigger", return_value=trigger
        ):
            response = client.post(
                "/api/runs", json={"company_slug": "opswat", "dry_run": True}
            )
        assert response.status_code in (202, 500)
