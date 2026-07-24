"""API endpoints for the web dashboard (JSON responses for AJAX)."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from job_board_scraper.core.database import get_session
from job_board_scraper.models import (
    AttemptStatus,
    Company,
    Job,
    ScrapeAttempt,
    ScrapeRun,
)
from job_board_scraper.models.job import JobStatus

router = APIRouter()


@router.get("/stats")
async def get_stats() -> dict[str, Any]:
    """Get dashboard statistics as JSON."""
    async with get_session() as session:
        # Total jobs
        total_jobs = await session.scalar(select(func.count(Job.id))) or 0

        # Open jobs
        open_jobs = (
            await session.scalar(
                select(func.count(Job.id)).where(Job.status == JobStatus.open.value)
            )
            or 0
        )

        # Total companies
        total_companies = await session.scalar(select(func.count(Company.id))) or 0

        # Active companies
        active_companies = (
            await session.scalar(
                select(func.count(Company.id)).where(Company.is_active == True)
            )
            or 0
        )

        # Total runs
        total_runs = await session.scalar(select(func.count(ScrapeRun.id))) or 0

        # Last run info
        last_run_result = await session.execute(
            select(ScrapeRun).order_by(ScrapeRun.started_at.desc()).limit(1)
        )
        last_run = last_run_result.scalar_one_or_none()

        # Jobs found in last run
        last_run_jobs = 0
        last_run_status = None
        if last_run:
            last_run_jobs = (
                await session.scalar(
                    select(func.coalesce(func.sum(ScrapeAttempt.jobs_found), 0)).where(
                        ScrapeAttempt.run_id == last_run.id
                    )
                )
                or 0
            )
            last_run_status = last_run.status

        return {
            "total_jobs": total_jobs,
            "open_jobs": open_jobs,
            "total_companies": total_companies,
            "active_companies": active_companies,
            "total_runs": total_runs,
            "last_run": {
                "id": last_run.id if last_run else None,
                "started_at": last_run.started_at.isoformat() if last_run else None,
                "jobs_found": last_run_jobs,
                "status": last_run_status,
            }
            if last_run
            else None,
        }


@router.get("/runs")
async def get_runs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """Get scrape runs as JSON with pagination."""
    async with get_session() as session:
        # Get total count
        total_count = await session.scalar(select(func.count(ScrapeRun.id))) or 0
        total_pages = max(1, (total_count + limit - 1) // limit)

        if page > total_pages:
            page = total_pages

        # Get runs
        offset = (page - 1) * limit
        result = await session.execute(
            select(ScrapeRun)
            .order_by(ScrapeRun.started_at.desc())
            .offset(offset)
            .limit(limit)
        )
        runs = list(result.scalars().all())

        # Enrich runs with attempt totals
        runs_data = []
        for run in runs:
            totals = await _get_run_totals(session, run.id)
            runs_data.append(
                {
                    "id": run.id,
                    "started_at": run.started_at.isoformat(),
                    "finished_at": run.finished_at.isoformat()
                    if run.finished_at
                    else None,
                    "duration_seconds": run.duration_seconds,
                    "status": run.status,
                    "triggered_by": run.triggered_by,
                    "notes": run.notes,
                    "jobs_found": totals["jobs_found"],
                    "new_jobs": totals["new_jobs"],
                    "closed_jobs": totals["closed_jobs"],
                    "failed": totals["failed"],
                }
            )

        return {
            "runs": runs_data,
            "page": page,
            "limit": limit,
            "total_count": total_count,
            "total_pages": total_pages,
        }


@router.get("/runs/{run_id}")
async def get_run_detail(run_id: int) -> dict[str, Any]:
    """Get details for a specific scrape run."""
    async with get_session() as session:
        # Get the run
        result = await session.execute(select(ScrapeRun).where(ScrapeRun.id == run_id))
        run = result.scalar_one_or_none()

        if not run:
            return {"error": "Run not found"}

        # Get totals
        totals = await _get_run_totals(session, run.id)

        # Get attempts with company info
        result = await session.execute(
            select(ScrapeAttempt, Company)
            .join(Company, ScrapeAttempt.company_id == Company.id)
            .where(ScrapeAttempt.run_id == run_id)
            .order_by(ScrapeAttempt.started_at)
        )

        attempts_data = []
        for attempt, company in result.all():
            attempts_data.append(
                {
                    "id": attempt.id,
                    "company_id": company.id,
                    "company_name": company.name,
                    "company_slug": company.slug,
                    "status": attempt.status,
                    "jobs_found": attempt.jobs_found,
                    "new_jobs": attempt.new_jobs,
                    "closed_jobs": attempt.closed_jobs,
                    "duration_seconds": attempt.duration_seconds,
                    "requests_made": attempt.requests_made,
                    "pages_fetched": attempt.pages_fetched,
                    "complete": attempt.complete,
                    "authoritative_snapshot": attempt.authoritative_snapshot,
                    "error_type": attempt.error_type,
                    "error_message": attempt.error_message,
                    "warnings": attempt.warnings,
                    "started_at": attempt.started_at.isoformat(),
                    "finished_at": attempt.finished_at.isoformat()
                    if attempt.finished_at
                    else None,
                }
            )

        return {
            "id": run.id,
            "started_at": run.started_at.isoformat(),
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "duration_seconds": run.duration_seconds,
            "status": run.status,
            "triggered_by": run.triggered_by,
            "notes": run.notes,
            "jobs_found": totals["jobs_found"],
            "new_jobs": totals["new_jobs"],
            "closed_jobs": totals["closed_jobs"],
            "failed": totals["failed"],
            "attempts": attempts_data,
        }


@router.get("/jobs")
async def get_jobs(
    company: str | None = Query(None),
    status: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
) -> dict[str, Any]:
    """Get jobs as JSON with filters and pagination."""
    async with get_session() as session:
        # Build query
        query = select(Job).join(Company, Job.company_id == Company.id)
        count_query = select(func.count(Job.id)).join(
            Company, Job.company_id == Company.id
        )

        if company:
            company_obj = await session.scalar(
                select(Company).where(Company.slug == company)
            )
            if company_obj:
                query = query.where(Job.company_id == company_obj.id)
                count_query = count_query.where(Job.company_id == company_obj.id)

        if status and status in [s.value for s in JobStatus]:
            query = query.where(Job.status == status)
            count_query = count_query.where(Job.status == status)

        if date_from:
            query = query.where(Job.date_posted >= date_from)
            count_query = count_query.where(Job.date_posted >= date_from)

        if date_to:
            query = query.where(Job.date_posted <= date_to)
            count_query = count_query.where(Job.date_posted <= date_to)

        # Get total count
        total_count = await session.scalar(count_query) or 0
        total_pages = max(1, (total_count + limit - 1) // limit)

        if page > total_pages:
            page = total_pages

        # Get jobs
        offset = (page - 1) * limit
        result = await session.execute(
            query.options(selectinload(Job.company))
            .order_by(Job.date_posted.desc().nullslast())
            .offset(offset)
            .limit(limit)
        )
        jobs = list(result.scalars().all())

        jobs_data = []
        for job in jobs:
            jobs_data.append(
                {
                    "id": job.id,
                    "title": job.title,
                    "location": job.location,
                    "url": job.url,
                    "status": job.status,
                    "date_posted": job.date_posted.isoformat()
                    if job.date_posted
                    else None,
                    "company": {
                        "id": job.company.id if job.company else None,
                        "name": job.company.name if job.company else "Unknown",
                        "slug": job.company.slug if job.company else "",
                    },
                }
            )

        return {
            "jobs": jobs_data,
            "page": page,
            "limit": limit,
            "total_count": total_count,
            "total_pages": total_pages,
            "filters": {
                "company": company,
                "status": status,
                "date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None,
            },
        }


@router.get("/companies")
async def get_companies(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """Get companies as JSON with pagination."""
    async with get_session() as session:
        # Get total count
        total_count = await session.scalar(select(func.count(Company.id))) or 0
        total_pages = max(1, (total_count + limit - 1) // limit)

        if page > total_pages:
            page = total_pages

        # Get companies
        offset = (page - 1) * limit
        result = await session.execute(
            select(Company).order_by(Company.name).offset(offset).limit(limit)
        )
        companies = list(result.scalars().all())

        # Enrich with job counts
        companies_data = []
        for company in companies:
            total_jobs = (
                await session.scalar(
                    select(func.count(Job.id)).where(Job.company_id == company.id)
                )
                or 0
            )
            open_jobs = (
                await session.scalar(
                    select(func.count(Job.id))
                    .where(Job.company_id == company.id)
                    .where(Job.status == JobStatus.open.value)
                )
                or 0
            )

            companies_data.append(
                {
                    "id": company.id,
                    "name": company.name,
                    "slug": company.slug,
                    "adapter_type": company.adapter_type,
                    "base_url": company.base_url,
                    "is_active": company.is_active,
                    "total_jobs": total_jobs,
                    "open_jobs": open_jobs,
                }
            )

        return {
            "companies": companies_data,
            "page": page,
            "limit": limit,
            "total_count": total_count,
            "total_pages": total_pages,
        }


async def _get_run_totals(session: AsyncSession, run_id: int) -> dict[str, int]:
    """Get aggregate totals for a run from its attempts."""
    result = await session.execute(
        select(
            func.coalesce(func.sum(ScrapeAttempt.jobs_found), 0),
            func.coalesce(func.sum(ScrapeAttempt.new_jobs), 0),
            func.coalesce(func.sum(ScrapeAttempt.closed_jobs), 0),
            func.count().filter(ScrapeAttempt.status == AttemptStatus.FAILED.value),
        ).where(ScrapeAttempt.run_id == run_id)
    )
    row = result.one()

    return {
        "jobs_found": int(row[0]),
        "new_jobs": int(row[1]),
        "closed_jobs": int(row[2]),
        "failed": int(row[3]),
    }
