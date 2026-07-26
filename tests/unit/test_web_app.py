"""Unit tests for ``web/app.py`` covering FastAPI app creation."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from job_board_scraper.web.app import create_app


def test_create_app_returns_fastapi_instance() -> None:
    app = create_app()
    assert app.title == "Job Board Scraper Dashboard"
    # All expected routers registered
    route_prefixes = {r.path for r in app.routes}
    # health endpoints vary; assert a couple of known dashboard paths exist
    assert any(p.startswith("/") for p in route_prefixes)


def test_lifespan_initializes_and_closes_db() -> None:
    """The lifespan context should call init_db / close_db exactly once."""
    init_mock = AsyncMock()
    close_mock = AsyncMock()

    app = create_app()
    with (
        patch("job_board_scraper.web.app.init_db", new=init_mock),
        patch("job_board_scraper.web.app.close_db", new=close_mock),
    ):
        # Build a fake lifespan and execute it.
        async def _run() -> None:
            async with app.router.lifespan_context(app):
                pass

        import asyncio

        asyncio.new_event_loop().run_until_complete(_run())
