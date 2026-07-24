"""FastAPI application for job-board-scraper web dashboard.

This module initializes the FastAPI application with Jinja2 templates,
static file serving, and all route modules.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from job_board_scraper.core.database import close_db, init_db
from job_board_scraper.web.routes import (
    api_router,
    companies_router,
    dashboard_router,
    jobs_router,
    runs_router,
)

# Package root directory
PACKAGE_ROOT = Path(__file__).parent

# Templates directory
TEMPLATES_DIR = PACKAGE_ROOT / "templates"

# Static files directory
STATIC_DIR = PACKAGE_ROOT / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifespan: startup and shutdown events."""
    # Startup: initialize database
    await init_db()
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

    # Include routers
    app.include_router(dashboard_router, prefix="", tags=["Dashboard"])
    app.include_router(runs_router, prefix="", tags=["Runs"])
    app.include_router(companies_router, prefix="", tags=["Companies"])
    app.include_router(jobs_router, prefix="", tags=["Jobs"])
    app.include_router(api_router, prefix="/api", tags=["API"])

    # Store templates in app state for access in routes
    app.state.templates = templates

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
