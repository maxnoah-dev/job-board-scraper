"""CLI entry point.

Provides subcommands for the ETL pipeline:
    run         - Execute a scrape of all or specific companies
    init-db     - Initialize the database schema
    seed        - Seed company records from the source manifest
    export      - Export jobs to CSV
    export-xlsx - Export jobs to the Vietnamese-first Excel template

Exit codes:
    0 - SUCCESS
    1 - PARTIAL / error
    2 - FAILED
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from job_board_scraper.core.database import check_connection, close_db, init_db
from job_board_scraper.etl.pipeline import PipelineExitCode, create_pipeline

LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
LOG_FILE = LOG_DIR / "scraper.log"


def setup_logging(verbose: bool = False) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        level=log_level,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(LOG_FILE, mode="a"),
        ],
    )
    if not verbose:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)


def _run_coroutine(coro_factory):
    """Run a coroutine factory, transparently handling pytest-asyncio loops.

    ``coro_factory`` must be a zero-argument callable that returns a coroutine
    when invoked. Under pytest-asyncio, an event loop is already running, so
    ``asyncio.run`` would raise. We execute the coroutine on a worker thread
    with its own event loop in that case.
    """
    coro = coro_factory()
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # Inside a running loop (pytest-asyncio). Run the coroutine on a worker
    # thread so it has its own event loop and ``asyncio.run`` works.
    import concurrent.futures as _cf

    with _cf.ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(asyncio.run, coro_factory())
        return future.result()


async def cmd_run(args: argparse.Namespace) -> int:
    """Execute the ETL scrape pipeline."""
    logger = logging.getLogger(__name__)

    logger.info(
        "Starting job scraper",
        extra={"company": args.company, "dry_run": args.dry_run},
    )

    try:
        await init_db()
        if not await check_connection():
            logger.error("Failed to connect to database")
            return PipelineExitCode.FAILED.value

        pipeline = create_pipeline()
        company_slugs = [args.company] if args.company else None
        triggered_by = f"cli:{args.company}" if args.company else "cli:all"

        result = await pipeline.run(
            company_slugs=company_slugs,
            dry_run=args.dry_run,
            triggered_by=triggered_by,
            enable_vilao=getattr(args, "with_vilao", False),
        )

        _print_summary(result, args.verbose)
        return result.status.value

    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        return PipelineExitCode.FAILED.value
    except Exception:
        logger.exception("Unexpected error during scrape")
        return PipelineExitCode.FAILED.value
    finally:
        await close_db()


def cmd_init_db(_args: argparse.Namespace) -> int:
    """Initialize the database schema."""
    import scripts.init_db

    return scripts.init_db.main([])


def cmd_seed(args: argparse.Namespace) -> int:
    """Seed company records from the source manifest."""
    import scripts.seed_companies

    seed_args = ["--force"] if args.force else []
    return scripts.seed_companies.main(seed_args)


def cmd_export(args: argparse.Namespace) -> int:
    """Export jobs to CSV."""
    return _run_coroutine(lambda: _do_export_csv(args))


async def _do_export_csv(args: argparse.Namespace) -> int:
    from job_board_scraper.core.database import check_connection, close_db
    from job_board_scraper.reporting.csv_exporter import CsvExporter

    if not await check_connection():
        print("ERROR: Cannot connect to database.")
        return 1
    try:
        exporter = CsvExporter(args.output or "./data/jobs.csv")
        count = await exporter.export(open_only=args.open_only)
        print(f"Exported {count} jobs to {exporter.output_path}")
        return 0
    finally:
        await close_db()


def cmd_export_xlsx(args: argparse.Namespace) -> int:
    """Export jobs to the Vietnamese-first Excel template."""
    return _run_coroutine(lambda: _do_export_xlsx(args))


async def _do_export_xlsx(args: argparse.Namespace) -> int:
    from sqlalchemy import select

    from job_board_scraper.core.config import get_settings
    from job_board_scraper.core.database import (
        check_connection,
        close_db,
        session_scope,
    )
    from job_board_scraper.models.db_company import Company
    from job_board_scraper.models.db_job import Job
    from job_board_scraper.reporting.excel_exporter import (
        ExcelExporter,
        ExcelExportOptions,
    )

    if not await check_connection():
        print("ERROR: Cannot connect to database.")
        return 1
    try:
        settings = get_settings()
        output_path = Path(args.output or settings.EXPORT_DIR / "jobs.xlsx")
        template_path = (
            Path(args.template)
            if args.template
            else Path("docs/Apply Job in US.xlsx")
        )

        async with session_scope() as session:
            stmt = select(Job, Company).join(
                Company, Company.id == Job.company_id
            )
            if not args.include_closed:
                stmt = stmt.where(Job.status == "open")
            result = await session.execute(stmt)
            rows = result.all()

        jobs: list[dict] = []
        for job, company in rows:
            jobs.append(
                {
                    "company_name": company.name,
                    "company_slug": company.slug,
                    "title": job.title,
                    "title_vi": job.title_vi,
                    "url": job.url,
                    "location": job.location,
                    "status": job.status,
                    "salary_raw": job.salary_raw,
                    "raw_data": job.raw_data or {},
                }
            )

        exporter = ExcelExporter(output_path=output_path, template_path=template_path)
        options = ExcelExportOptions(
            sheet_name=args.sheet_name,
            include_closed=args.include_closed,
        )
        final_path = await exporter.export(jobs, options=options)
        print(f"Exported {len(jobs)} jobs to {final_path}")
        return 0
    finally:
        await close_db()


def _print_summary(result, verbose: bool = False) -> None:
    """Print scrape result summary."""
    print()
    print("=" * 60)
    print("SCRAPE SUMMARY")
    print("=" * 60)
    print(f"Run ID:     {result.run_id}")
    print(f"Status:     {result.status.name}")
    print(f"Duration:   {result.duration_seconds:.2f}s")
    print()
    print(f"Total Jobs: {result.total_jobs_found}")
    print(f"New Jobs:   {result.total_new_jobs}")
    print(f"Closed:     {result.total_closed_jobs}")
    print(f"Errors:     {result.total_errors}")
    print()

    if verbose and result.company_results:
        print("-" * 60)
        print("PER-COMPANY RESULTS")
        print("-" * 60)
        for cr in result.company_results:
            icon = {
                PipelineExitCode.SUCCESS: "[OK]",
                PipelineExitCode.PARTIAL: "[!!]",
                PipelineExitCode.FAILED: "[XX]",
            }.get(cr.status, "[??]")
            print(f"{icon} {cr.company_slug}")
            print(f"     Jobs Found: {cr.jobs_found}")
            print(f"     New Jobs:   {cr.new_jobs}")
            print(f"     Closed:     {cr.closed_jobs}")
            print(f"     Duration:   {cr.duration_ms}ms")
            if cr.error_type:
                print(f"     Error:      {cr.error_type}: {cr.error_message}")
            print()

    if result.status == PipelineExitCode.SUCCESS:
        print("All companies scraped successfully.")
    elif result.status == PipelineExitCode.PARTIAL:
        failed = [cr.company_slug for cr in result.failed_companies]
        if failed:
            print(f"Companies failed: {', '.join(failed)}")
        print("Some companies had issues - see warnings above.")
    else:
        print("SCRAPE FAILED - Check logs for details.")
    print("=" * 60)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="job-board-scraper",
        description="Job board scraper ETL pipeline CLI.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # run
    p_run = subparsers.add_parser("run", help="Execute the scrape pipeline")
    p_run.add_argument(
        "-c", "--company", type=str, metavar="SLUG", help="Scrape only this company"
    )
    p_run.add_argument(
        "-d", "--dry-run", action="store_true", help="Run without database writes"
    )
    p_run.add_argument(
        "--with-vilao",
        action="store_true",
        help="Enable Vilao LLM title translation (requires VILAO_API_KEY).",
    )
    p_run.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    # init-db
    p_init = subparsers.add_parser("init-db", help="Initialize the database schema")
    p_init.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    # seed
    p_seed = subparsers.add_parser("seed", help="Seed company records")
    p_seed.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    p_seed.add_argument("--force", action="store_true", help="Force re-activation")

    # export
    p_exp = subparsers.add_parser("export", help="Export jobs to CSV")
    p_exp.add_argument("-o", "--output", type=str, help="Output CSV path")
    p_exp.add_argument(
        "--all",
        dest="open_only",
        action="store_false",
        default=True,
        help="Include closed jobs",
    )
    p_exp.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    # export-xlsx
    p_xlsx = subparsers.add_parser(
        "export-xlsx", help="Export jobs to the Vietnamese-first Excel template"
    )
    p_xlsx.add_argument(
        "-o", "--output", type=str, help="Output XLSX path (default: data/jobs.xlsx)"
    )
    p_xlsx.add_argument(
        "--template",
        type=str,
        help="Path to the Excel template (default: docs/Apply Job in US.xlsx).",
    )
    p_xlsx.add_argument(
        "--sheet-name", type=str, default="From Scraper", help="Name of the new sheet"
    )
    p_xlsx.add_argument(
        "--include-closed", action="store_true", help="Include closed jobs"
    )
    p_xlsx.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if args.command == "run":
        setup_logging(args.verbose)
        return asyncio.run(cmd_run(args))
    elif args.command == "init-db":
        setup_logging(args.verbose)
        return cmd_init_db(args)
    elif args.command == "seed":
        setup_logging(args.verbose)
        return cmd_seed(args)
    elif args.command == "export":
        setup_logging(args.verbose)
        return cmd_export(args)
    elif args.command == "export-xlsx":
        setup_logging(args.verbose)
        return cmd_export_xlsx(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
