"""Runs routes for the web dashboard."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from job_board_scraper.core.database import session_scope
from job_board_scraper.models import AttemptStatus, Company, ScrapeAttempt, ScrapeRun

router = APIRouter()

ITEMS_PER_PAGE = 20


@router.get("/runs", response_class=HTMLResponse, name="list_runs")
async def list_runs(
    request: Request,
    page: int = Query(1, ge=1),
) -> HTMLResponse:
    """Render the list of scrape runs."""
    templates = request.app.state.templates

    async with session_scope() as session:
        # Get total count
        total_count = await session.scalar(select(func.count(ScrapeRun.id)))
        total_pages = max(1, (total_count + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

        # Ensure page is within bounds
        if page > total_pages:
            page = total_pages

        # Get runs with pagination
        offset = (page - 1) * ITEMS_PER_PAGE
        result = await session.execute(
            select(ScrapeRun)
            .order_by(ScrapeRun.started_at.desc())
            .offset(offset)
            .limit(ITEMS_PER_PAGE)
        )
        runs = list(result.scalars().all())

        # Enrich each run with totals
        for run in runs:
            await _enrich_run_totals(session, run)

    return templates.TemplateResponse(
        "runs.html",
        {
            "request": request,
            "runs": runs,
            "page": page,
            "total_pages": total_pages,
        },
    )


@router.get("/runs/{run_id}", response_class=HTMLResponse, name="run_detail")
async def run_detail(
    request: Request,
    run_id: int,
) -> HTMLResponse:
    """Render the detail page for a single scrape run."""
    templates = request.app.state.templates

    async with session_scope() as session:
        # Get the run
        result = await session.execute(select(ScrapeRun).where(ScrapeRun.id == run_id))
        run = result.scalar_one_or_none()

        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        # Enrich with totals
        await _enrich_run_totals(session, run)

        # Get attempts with company info
        result = await session.execute(
            select(ScrapeAttempt, Company)
            .join(Company, ScrapeAttempt.company_id == Company.id)
            .where(ScrapeAttempt.run_id == run_id)
            .order_by(ScrapeAttempt.started_at)
        )
        attempts = []
        for attempt, company in result.all():
            attempt_dict = {
                "id": attempt.id,
                "status": attempt.status,
                "jobs_found": attempt.jobs_found,
                "new_jobs": attempt.new_jobs,
                "closed_jobs": attempt.closed_jobs,
                "duration_seconds": attempt.duration_seconds,
                "requests_made": attempt.requests_made,
                "error_type": attempt.error_type,
                "error_message": attempt.error_message,
                "company_name": company.name,
                "company_slug": company.slug,
            }
            attempts.append(attempt_dict)

    return templates.TemplateResponse(
        "run_detail.html",
        {
            "request": request,
            "run": run,
            "attempts": attempts,
        },
    )


async def _enrich_run_totals(session: AsyncSession, run: ScrapeRun) -> None:
    """Add total fields to a run from its attempts."""
    result = await session.execute(
        select(
            func.coalesce(func.sum(ScrapeAttempt.jobs_found), 0),
            func.coalesce(func.sum(ScrapeAttempt.new_jobs), 0),
            func.coalesce(func.sum(ScrapeAttempt.closed_jobs), 0),
            func.count().filter(ScrapeAttempt.status == AttemptStatus.FAILED.value),
        ).where(ScrapeAttempt.run_id == run.id)
    )
    row = result.one()

    run.total_jobs_found = row[0]
    run.total_new_jobs = row[1]
    run.total_closed_jobs = row[2]
    run.total_failed = row[3]
