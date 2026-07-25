"""Dashboard routes for the web dashboard."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from job_board_scraper.core.database import session_scope
from job_board_scraper.models import Company, Job, ScrapeRun
from job_board_scraper.models.job import JobStatus

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
@router.get("/dashboard", response_class=HTMLResponse, name="dashboard")
async def dashboard(request: Request) -> HTMLResponse:
    """Render the main dashboard page."""
    templates = request.app.state.templates

    async with session_scope() as session:
        # Get stats
        stats = await _get_stats(session)

        # Get last run
        last_run = await _get_last_run(session)
        if last_run:
            await _enrich_run_totals(session, last_run)

        # Get recent runs
        recent_runs = await _get_recent_runs(session, limit=10)
        for run in recent_runs:
            await _enrich_run_totals(session, run)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "stats": stats,
            "last_run": last_run,
            "recent_runs": recent_runs,
        },
    )


async def _get_stats(session: AsyncSession) -> dict:
    """Get dashboard statistics."""
    # Total jobs
    total_jobs = await session.scalar(select(func.count(Job.id)))

    # Open jobs
    open_jobs = await session.scalar(
        select(func.count(Job.id)).where(Job.status == JobStatus.open.value)
    )

    # Total companies
    total_companies = await session.scalar(select(func.count(Company.id)))

    # Total runs
    total_runs = await session.scalar(select(func.count(ScrapeRun.id)))

    return {
        "total_jobs": total_jobs or 0,
        "open_jobs": open_jobs or 0,
        "total_companies": total_companies or 0,
        "total_runs": total_runs or 0,
    }


async def _get_last_run(session: AsyncSession) -> ScrapeRun | None:
    """Get the most recent scrape run."""
    result = await session.execute(
        select(ScrapeRun).order_by(ScrapeRun.started_at.desc()).limit(1)
    )
    return result.scalar_one_or_none()


async def _get_recent_runs(session: AsyncSession, limit: int = 10) -> list[ScrapeRun]:
    """Get recent scrape runs."""
    result = await session.execute(
        select(ScrapeRun).order_by(ScrapeRun.started_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def _enrich_run_totals(session: AsyncSession, run: ScrapeRun) -> None:
    """Add total fields to a run from its attempts."""
    from job_board_scraper.models import AttemptStatus, ScrapeAttempt

    result = await session.execute(
        select(
            func.sum(ScrapeAttempt.jobs_found),
            func.sum(ScrapeAttempt.new_jobs),
            func.sum(ScrapeAttempt.closed_jobs),
            func.count(ScrapeAttempt.id).filter(
                ScrapeAttempt.status == AttemptStatus.FAILED.value
            ),
        ).where(ScrapeAttempt.run_id == run.id)
    )
    row = result.one()

    run.total_jobs_found = row[0] or 0
    run.total_new_jobs = row[1] or 0
    run.total_closed_jobs = row[2] or 0
    run.total_failed = row[3] or 0
