"""Companies routes for the web dashboard."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from job_board_scraper.core.database import get_session
from job_board_scraper.models import Company, Job, ScrapeAttempt
from job_board_scraper.models.job import JobStatus

router = APIRouter()

ITEMS_PER_PAGE = 20


@router.get("/companies", response_class=HTMLResponse, name="list_companies")
async def list_companies(
    request: Request,
    page: int = Query(1, ge=1),
) -> HTMLResponse:
    """Render the list of companies."""
    templates = request.app.state.templates

    async with get_session() as session:
        # Get total count
        total_count = await session.scalar(select(func.count(Company.id)))
        total_pages = max(1, (total_count + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

        # Ensure page is within bounds
        if page > total_pages:
            page = total_pages

        # Get companies with pagination
        offset = (page - 1) * ITEMS_PER_PAGE
        result = await session.execute(
            select(Company).order_by(Company.name).offset(offset).limit(ITEMS_PER_PAGE)
        )
        companies = list(result.scalars().all())

        # Enrich with job counts
        for company in companies:
            await _enrich_company_stats(session, company)

    return templates.TemplateResponse(
        "companies.html",
        {
            "request": request,
            "companies": companies,
            "page": page,
            "total_pages": total_pages,
        },
    )


@router.get("/companies/{slug}", response_class=HTMLResponse, name="company_detail")
async def company_detail(
    request: Request,
    slug: str,
) -> HTMLResponse:
    """Render the detail page for a company."""
    templates = request.app.state.templates

    async with get_session() as session:
        # Get the company
        result = await session.execute(select(Company).where(Company.slug == slug))
        company = result.scalar_one_or_none()

        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        # Enrich with stats
        await _enrich_company_stats(session, company)

        # Get recent attempts
        result = await session.execute(
            select(ScrapeAttempt)
            .where(ScrapeAttempt.company_id == company.id)
            .order_by(ScrapeAttempt.started_at.desc())
            .limit(10)
        )
        attempts = list(result.scalars().all())

    return templates.TemplateResponse(
        "company_detail.html",
        {
            "request": request,
            "company": company,
            "attempts": attempts,
        },
    )


@router.get("/companies/{slug}/jobs", response_class=HTMLResponse, name="company_jobs")
async def company_jobs(
    request: Request,
    slug: str,
    page: int = Query(1, ge=1),
) -> HTMLResponse:
    """Render jobs for a specific company."""
    templates = request.app.state.templates

    async with get_session() as session:
        # Get the company
        result = await session.execute(select(Company).where(Company.slug == slug))
        company = result.scalar_one_or_none()

        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        # Get companies list for filter
        companies_result = await session.execute(select(Company).order_by(Company.name))
        companies = list(companies_result.scalars().all())

        # Get total count for this company
        total_count = await session.scalar(
            select(func.count(Job.id)).where(Job.company_id == company.id)
        )
        total_pages = max(1, (total_count + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

        if page > total_pages:
            page = total_pages

        # Get jobs
        offset = (page - 1) * ITEMS_PER_PAGE
        result = await session.execute(
            select(Job)
            .where(Job.company_id == company.id)
            .order_by(Job.date_posted.desc().nullslast())
            .offset(offset)
            .limit(ITEMS_PER_PAGE)
        )
        jobs = list(result.scalars().all())

        # Enrich with company name
        for job in jobs:
            job.company_name = company.name
            job.company_slug = company.slug

    # Build filter params for pagination
    filter_params = {"company": slug}

    return templates.TemplateResponse(
        "jobs.html",
        {
            "request": request,
            "jobs": [_job_to_dict(job) for job in jobs],
            "companies": [{"slug": c.slug, "name": c.name} for c in companies],
            "filters": {
                "company": slug,
                "status": None,
                "date_from": None,
                "date_to": None,
            },
            "filter_params": filter_params,
            "page": page,
            "total_pages": total_pages,
        },
    )


async def _enrich_company_stats(session: AsyncSession, company: Company) -> None:
    """Add job counts to a company."""

    # Total jobs
    total_jobs = await session.scalar(
        select(func.count(Job.id)).where(Job.company_id == company.id)
    )

    # Open jobs
    open_jobs = await session.scalar(
        select(func.count(Job.id))
        .where(Job.company_id == company.id)
        .where(Job.status == JobStatus.open.value)
    )

    # Closed jobs
    closed_jobs = await session.scalar(
        select(func.count(Job.id))
        .where(Job.company_id == company.id)
        .where(Job.status == JobStatus.closed.value)
    )

    # Last run
    last_attempt = await session.scalar(
        select(ScrapeAttempt)
        .where(ScrapeAttempt.company_id == company.id)
        .order_by(ScrapeAttempt.started_at.desc())
        .limit(1)
    )

    company.total_jobs = total_jobs or 0
    company.open_jobs = open_jobs or 0
    company.closed_jobs = closed_jobs or 0
    company.last_run_at = last_attempt.started_at if last_attempt else None


def _job_to_dict(job: Job) -> dict:
    """Convert a Job model to a dictionary for template rendering."""
    return {
        "id": job.id,
        "title": job.title,
        "location": job.location,
        "url": job.url,
        "status": job.status,
        "date_posted": job.date_posted,
        "company_name": getattr(job, "company_name", ""),
        "company_slug": getattr(job, "company_slug", ""),
    }
