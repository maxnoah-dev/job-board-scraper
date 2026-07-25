"""FastAPI application for job-board-scraper web dashboard.

This module initializes the FastAPI application with Jinja2 templates,
static file serving, and all route modules.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from job_board_scraper.core.database import close_db, init_db
from job_board_scraper.web.i18n import DEFAULT_LOCALE, SUPPORTED_LOCALES, get_translator
from job_board_scraper.web.routes import (
    api_router,
    companies_router,
    dashboard_router,
    jobs_router,
    runs_router,
)
from job_board_scraper.web.services import get_trigger

# Package root directory
PACKAGE_ROOT = Path(__file__).parent

# Templates directory
TEMPLATES_DIR = PACKAGE_ROOT / "templates"

# Static files directory
STATIC_DIR = PACKAGE_ROOT / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifespan: startup and shutdown events."""
    # Startup: initialize database + the scrape trigger singleton so
    # the API endpoints always see the same instance.
    await init_db()
    app.state.scrape_trigger = get_trigger()
    yield
    # Shutdown: close database connections
    await close_db()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Job Board Scraper Dashboard",
        description="Web dashboard for monitoring job scraping operations",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount static files
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Configure Jinja2 templates
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    # Register translation helper as a Jinja global so any template
    # can call ``{{ t('nav.dashboard') }}`` without explicitly passing
    # the locale into the context. The default locale is used for the
    # initial SSR render; the frontend i18n.js swaps strings on the
    # fly when the user changes language.
    templates.env.globals["t"] = get_translator(DEFAULT_LOCALE)
    templates.env.globals["current_locale"] = DEFAULT_LOCALE
    templates.env.globals["supported_locales"] = SUPPORTED_LOCALES

    # Include routers
    app.include_router(dashboard_router, prefix="", tags=["Dashboard"])
    app.include_router(runs_router, prefix="", tags=["Runs"])
    app.include_router(companies_router, prefix="", tags=["Companies"])
    app.include_router(jobs_router, prefix="", tags=["Jobs"])
    app.include_router(api_router, prefix="/api", tags=["API"])

    # Store templates in app state for access in routes
    app.state.templates = templates

    # Endpoint that exposes locale JSON to the frontend so i18n.js
    # can swap strings without a full page reload.
    import json

    from job_board_scraper.web.i18n.translations import _load_locale

    @app.get("/api/i18n/{locale}", tags=["API"])
    async def get_locale(locale: str) -> Response:
        if locale not in SUPPORTED_LOCALES:
            locale = DEFAULT_LOCALE
        data = _load_locale(locale)
        return Response(
            content=json.dumps(data, ensure_ascii=False),
            media_type="application/json",
        )

    return app


# Application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "job_board_scraper.web.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
