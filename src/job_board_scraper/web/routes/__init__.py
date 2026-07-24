"""Routes package."""

from job_board_scraper.web.routes.api import router as api_router
from job_board_scraper.web.routes.companies import router as companies_router
from job_board_scraper.web.routes.dashboard import router as dashboard_router
from job_board_scraper.web.routes.jobs import router as jobs_router
from job_board_scraper.web.routes.runs import router as runs_router

__all__ = [
    "dashboard_router",
    "runs_router",
    "companies_router",
    "jobs_router",
    "api_router",
]
