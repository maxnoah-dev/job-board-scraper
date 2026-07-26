"""Regression tests for the URL-building bug in pagination templates.

Bug: clicking ``/jobs`` or ``/runs`` raised ``Internal Server Error``
because the Jinja ``url_for`` helper from Starlette passes every kwarg
as a *path* parameter. Routes like ``list_runs -> /runs`` accept zero
path params but the template called::

    {{url_for("list_runs", page=p)}}

so Starlette raised ``NoMatchFound: No route exists for name "list_runs"
and params "page"`` and the page 500'd.

The fix introduces a custom ``url_for`` helper that splits kwargs into
path params (consumed by the route) and query params (appended to the
URL as a query string), so templates can keep calling
``url_for('list_runs', page=p)`` without changes.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from job_board_scraper.core.base import Base  # noqa: E402
from job_board_scraper.core.database import get_session_factory  # noqa: E402

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


async def _seed_run(
    session_factory: Any,
    *,
    run_id: int,
    status: str = "success",
    started_at: datetime | None = None,
) -> None:
    started_at = started_at or datetime.now(UTC)
    async with session_factory() as session:
        await session.execute(
            insert(
                __import__(
                    "job_board_scraper.models",
                    fromlist=["ScrapeRun"],
                ).ScrapeRun
            ).values(
                id=run_id,
                started_at=started_at,
                finished_at=started_at,
                status=status,
                triggered_by="ui",
            )
        )
        await session.commit()


_seeded_company_slugs: set[str] = set()


@pytest.fixture(autouse=True)
def _reset_seeded_company_slugs() -> Any:
    """Reset the seeded-company tracker before every test for isolation."""
    _seeded_company_slugs.clear()
    yield
    _seeded_company_slugs.clear()


async def _seed_job(
    session_factory: Any,
    *,
    job_id: int,
    company_id: int,
    company_slug: str,
    title: str,
    url: str,
    status: str = "open",
) -> None:
    async with session_factory() as session:
        if company_slug not in _seeded_company_slugs:
            await session.execute(
                insert(
                    __import__(
                        "job_board_scraper.models",
                        fromlist=["Company"],
                    ).Company
                ).values(
                    id=company_id,
                    name=f"Co {company_slug}",
                    slug=company_slug,
                    adapter_type="api",
                    base_url=f"https://api.{company_slug}.example",
                    is_active=True,
                    authoritative=True,
                )
            )
            _seeded_company_slugs.add(company_slug)
        await session.execute(
            insert(
                __import__(
                    "job_board_scraper.models",
                    fromlist=["Job"],
                ).Job
            ).values(
                id=job_id,
                company_id=company_id,
                title=title,
                location="Remote",
                url=url,
                canonical_url=url,
                status=status,
                date_posted=datetime.now(UTC).date(),
            )
        )
        await session.commit()


async def _get_response(path: str, setup_db: Any) -> Any:
    """Seed + GET a page through the FastAPI app and return the response."""
    from job_board_scraper.web.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://test") as client,
        app.router.lifespan_context(app),
    ):
        return await client.get(path)


@pytest.mark.asyncio
async def test_runs_page_renders_with_enough_rows_for_pagination(
    setup_db: Any,
) -> None:
    """``GET /runs`` returns 200 once we have more than 20 runs.

    With 21+ rows the template renders the pagination block, which calls
    ``url_for('list_runs', page=p)``. Before the fix this raised
    ``NoMatchFound`` and the page returned 500.
    """
    for i in range(1, 22):
        await _seed_run(setup_db, run_id=i)

    resp = await _get_response("/runs", setup_db)

    assert resp.status_code == 200, resp.text
    body = resp.text
    # Pagination block uses page=2 once we have more than ITEMS_PER_PAGE rows.
    assert (
        "?page=2" in body or "page=2" in body
    ), "Pagination link should reference page=2 once there are >20 rows"


@pytest.mark.asyncio
async def test_jobs_page_renders_with_enough_rows_for_pagination(
    setup_db: Any,
) -> None:
    """``GET /jobs`` returns 200 once we have more than 25 jobs."""
    for i in range(1, 27):
        await _seed_job(
            setup_db,
            job_id=i,
            company_id=1,
            company_slug="acme",
            title=f"Engineer {i}",
            url=f"https://acme.example/jobs/{i}",
        )

    resp = await _get_response("/jobs", setup_db)

    assert resp.status_code == 200, resp.text
    assert (
        "?page=2" in resp.text or "page=2" in resp.text
    ), "Pagination link should reference page=2 once there are >25 jobs"


@pytest.mark.asyncio
async def test_jobs_page_preserves_filters_in_pagination_links(
    setup_db: Any,
) -> None:
    """When filters are active, pagination links keep them as query params."""
    for i in range(1, 27):
        await _seed_job(
            setup_db,
            job_id=i,
            company_id=1,
            company_slug="acme",
            title=f"Engineer {i}",
            url=f"https://acme.example/jobs/{i}",
        )

    resp = await _get_response("/jobs?company=acme&status=open", setup_db)

    assert resp.status_code == 200, resp.text
    body = resp.text
    assert "company=acme" in body, "company filter must survive pagination links"
    assert "status=open" in body, "status filter must survive pagination links"
    assert "page=2" in body, "pagination link should still reference page=2"


@pytest.mark.asyncio
async def test_runs_page_does_not_raise_no_match_found(
    setup_db: Any,
) -> None:
    """Direct regression guard: ensure the traceback text is not in the response."""
    for i in range(1, 22):
        await _seed_run(setup_db, run_id=i)

    resp = await _get_response("/runs", setup_db)

    assert resp.status_code == 200, resp.text
    assert "NoMatchFound" not in resp.text
    assert "Internal Server Error" not in resp.text
