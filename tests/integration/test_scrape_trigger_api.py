"""Integration tests for the manual scrape trigger API.

Tests the POST /api/runs endpoint that starts a scrape from the UI.
Covers:
- Starting a scrape with no company filter (run all active)
- Starting a scrape for a specific company slug
- Rejecting duplicate starts while a run is in progress (409)
- Surfacing current run status via GET /api/runs/status

Strategy: drive the ScrapeTrigger service directly + spin up the FastAPI
app to verify the endpoints are wired correctly. The trigger is reset
between tests so concurrency state doesn't leak.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from job_board_scraper.core.base import Base
from job_board_scraper.core.database import get_session_factory

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_engine():
    engine = create_async_engine(
        TEST_DB_URL,
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    yield engine
    await engine.dispose()


@pytest.fixture
async def setup_db(test_engine):
    """Bind the global session factory to a fresh in-memory schema."""
    session_factory = get_session_factory()
    original_bind = session_factory.kw.get("bind")
    session_factory.configure(bind=test_engine)

    from job_board_scraper.models import (  # noqa: F401
        db_company,
        db_job,
        db_scrape_attempt,
        db_scrape_run,
    )

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield session_factory

    session_factory.configure(bind=original_bind)


@pytest.fixture
def reset_trigger():
    """Reset the module-level ScrapeTrigger singleton between tests."""
    import job_board_scraper.web.services.scrape_trigger as mod

    mod._trigger = None
    yield
    mod._trigger = None


@pytest.fixture
async def seed_company(setup_db):
    factory = setup_db
    async with factory() as session:
        await session.execute(
            insert(__import__("job_board_scraper.models", fromlist=["Company"]).Company).values(
                name="Trigger Co",
                slug="triggerco",
                adapter_type="api",
                base_url="https://api.triggerco.example",
                is_active=True,
                authoritative=True,
            )
        )
        await session.commit()


def make_fake_pipeline(behaviour):
    """Build a mock pipeline whose ``run`` honours ``behaviour``."""
    fake = AsyncMock()
    fake.run = AsyncMock(side_effect=behaviour)
    return fake


@pytest.mark.asyncio
async def test_start_all_companies_returns_run_id(
    setup_db, seed_company, reset_trigger
):
    """POST /api/runs with no company filter returns 202 + run_id."""
    entered = asyncio.Event()

    async def short_run(**_k):
        entered.set()
        return {"run_id": 1, "status": "success"}

    pipeline = make_fake_pipeline(short_run)

    with patch(
        "job_board_scraper.web.services.scrape_trigger.create_pipeline",
        return_value=pipeline,
    ):
        from job_board_scraper.web.app import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:  # noqa: SIM117
            async with app.router.lifespan_context(app):
                resp = await client.post("/api/runs", json={})
                await asyncio.wait_for(entered.wait(), timeout=2)

        assert resp.status_code == 202, resp.text
        body = resp.json()
        assert "run_id" in body
        assert body["triggered_by"] == "ui"
        assert body["state"] == "running"


@pytest.mark.asyncio
async def test_start_specific_company(setup_db, seed_company, reset_trigger):
    """POST /api/runs with company_slug runs only that company."""
    entered = asyncio.Event()

    async def short_run(**_k):
        entered.set()
        return {"run_id": 1, "status": "success"}

    pipeline = make_fake_pipeline(short_run)

    with patch(
        "job_board_scraper.web.services.scrape_trigger.create_pipeline",
        return_value=pipeline,
    ):
        from job_board_scraper.web.app import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:  # noqa: SIM117
            async with app.router.lifespan_context(app):
                resp = await client.post(
                    "/api/runs", json={"company_slug": "triggerco"}
                )

                # Pump the loop so the background task runs to completion.
                await asyncio.wait_for(entered.wait(), timeout=2)

        assert resp.status_code == 202, resp.text
        body = resp.json()
        assert body["company_slug"] == "triggerco"

        # The pipeline should have received the slug list.
        assert pipeline.run.await_count >= 1
        kwargs = pipeline.run.await_args.kwargs
        assert kwargs["company_slugs"] == ["triggerco"]
        assert kwargs["triggered_by"] == "ui"


@pytest.mark.asyncio
async def test_second_start_returns_409_when_running(
    setup_db, seed_company, reset_trigger
):
    """A second POST while the first is still running must be refused."""
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_run(**_k):
        started.set()
        await release.wait()
        return {"run_id": 1, "status": "success"}

    pipeline = make_fake_pipeline(slow_run)

    with patch(
        "job_board_scraper.web.services.scrape_trigger.create_pipeline",
        return_value=pipeline,
    ):
        from job_board_scraper.web.app import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:  # noqa: SIM117
            async with app.router.lifespan_context(app):
                first = await client.post("/api/runs", json={})
                assert first.status_code == 202

                # Wait until pipeline.run has actually been entered.
                await asyncio.wait_for(started.wait(), timeout=2)

                second = await client.post("/api/runs", json={})
                assert second.status_code == 409
                assert "already" in second.json()["detail"].lower()

                # Release the pipeline so lifespan shutdown doesn't hang.
                release.set()


@pytest.mark.asyncio
async def test_status_idle_when_nothing_running(setup_db, reset_trigger):
    """GET /api/runs/status reports idle when no run is in flight."""
    from job_board_scraper.web.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:  # noqa: SIM117
        async with app.router.lifespan_context(app):
            resp = await client.get("/api/runs/status")

    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "idle"
    assert body["run_id"] is None


@pytest.mark.asyncio
async def test_status_running_during_run(setup_db, seed_company, reset_trigger):
    """While a run is in progress, status reports running + run_id."""
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_run(**_k):
        started.set()
        await release.wait()
        return {"run_id": 1, "status": "success"}

    pipeline = make_fake_pipeline(slow_run)

    with patch(
        "job_board_scraper.web.services.scrape_trigger.create_pipeline",
        return_value=pipeline,
    ):
        from job_board_scraper.web.app import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:  # noqa: SIM117
            async with app.router.lifespan_context(app):
                await client.post("/api/runs", json={})

                await asyncio.wait_for(started.wait(), timeout=2)

                resp = await client.get("/api/runs/status")
                assert resp.status_code == 200
                body = resp.json()
                assert body["state"] == "running"
                assert body["run_id"] is not None

                release.set()
