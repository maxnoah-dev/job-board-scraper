"""Jobs routes for the web dashboard."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from job_board_scraper.core.database import get_session
from job_board_scraper.models import Company, Job
from job_board_scraper.models.job import JobStatus
from job_board_scraper.web.routes.companies import _job_to_dict

router = APIRouter()

ITEMS_PER_PAGE = 25


@router.get("/jobs", response_class=HTMLResponse, name="list_jobs")
async def list_jobs(
    request: Request,
    company: str | None = Query(None),
    status: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    page: int = Query(1, ge=1),
) -> HTMLResponse:
    """Render the list of jobs with filters."""
    templates = request.app.state.templates

    async with get_session() as session:
        # Get all companies for filter dropdown
        companies_result = await session.execute(select(Company).order_by(Company.name))
        companies = list(companies_result.scalars().all())

        # Build query with filters
        query = select(Job).join(Company, Job.company_id == Company.id)
        count_query = select(func.count(Job.id)).join(
            Company, Job.company_id == Company.id
        )

        # Apply filters
        filters: dict[str, Any] = {"company": company, "status": status}

        if company:
            company_obj = await session.scalar(
                select(Company).where(Company.slug == company)
            )
            if company_obj:
                query = query.where(Job.company_id == company_obj.id)
                count_query = count_query.where(Job.company_id == company_obj.id)

        if status:
            if status in [s.value for s in JobStatus]:
                query = query.where(Job.status == status)
                count_query = count_query.where(Job.status == status)

        if date_from:
            query = query.where(Job.date_posted >= date_from)
            count_query = count_query.where(Job.date_posted >= date_from)
            filters["date_from"] = date_from.isoformat()

        if date_to:
            query = query.where(Job.date_posted <= date_to)
            count_query = count_query.where(Job.date_posted <= date_to)
            filters["date_to"] = date_to.isoformat()

        # Get total count
        total_count = await session.scalar(count_query)
        total_pages = max(1, (total_count + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

        if page > total_pages:
            page = total_pages

        # Get jobs with company info
        offset = (page - 1) * ITEMS_PER_PAGE
        result = await session.execute(
            query.options(selectinload(Job.company))
            .order_by(Job.date_posted.desc().nullslast())
            .offset(offset)
            .limit(ITEMS_PER_PAGE)
        )
        jobs = list(result.scalars().all())

        # Enrich with company info
        jobs_data = []
        for job in jobs:
            job_dict = _job_to_dict(job)
            job_dict["company_name"] = job.company.name if job.company else "Unknown"
            job_dict["company_slug"] = job.company.slug if job.company else ""
            jobs_data.append(job_dict)

    # Build filter params for pagination
    filter_params = {}
    if company:
        filter_params["company"] = company
    if status:
        filter_params["status"] = status
    if date_from:
        filter_params["date_from"] = filters["date_from"]
    if date_to:
        filter_params["date_to"] = filters["date_to"]

    return templates.TemplateResponse(
        "jobs.html",
        {
            "request": request,
            "jobs": jobs_data,
            "companies": [{"slug": c.slug, "name": c.name} for c in companies],
            "filters": filters,
            "filter_params": filter_params,
            "page": page,
            "total_pages": total_pages,
        },
    )
