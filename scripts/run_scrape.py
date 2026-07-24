"""CLI entrypoint for running job scrapes.

Usage:
    python scripts/run_scrape.py                    # Run all companies
    python scripts/run_scrape.py --company opswat    # Run single company
    python scripts/run_scrape.py --dry-run           # Test without DB writes
    python scripts/run_scrape.py -v                  # Verbose output

Exit codes:
    0 - SUCCESS: All companies scraped successfully
    1 - PARTIAL: Some companies had issues (partial failure)
    2 - FAILED: All companies failed or pipeline crashed
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from job_board_scraper.core.database import check_connection, close_db, init_db
from job_board_scraper.etl.pipeline import (
    PipelineExitCode,
    create_pipeline,
)

LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
LOG_FILE = LOG_DIR / "scraper.log"


def setup_logging(verbose: bool = False) -> None:
    """Configure structured logging.

    Args:
        verbose: Enable debug level logging
    """
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


async def async_main(args: argparse.Namespace) -> int:
    """Async main entrypoint.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code
    """
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    logger.info(
        "Starting job scraper",
        extra={
            "company": args.company,
            "dry_run": args.dry_run,
        },
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
        )

        print_summary(result, args.verbose)

        return result.status.value

    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        return PipelineExitCode.FAILED.value
    except Exception:
        logger.exception("Unexpected error during scrape")
        return PipelineExitCode.FAILED.value
    finally:
        await close_db()


def print_summary(result, verbose: bool = False) -> None:
    """Print a summary of the scrape results.

    Args:
        result: PipelineResult from the scrape
        verbose: Include detailed per-company output
    """
    print()
    print("=" * 60)
    print("SCRAPE SUMMARY")
    print("=" * 60)
    print(f"Run ID:        {result.run_id}")
    print(f"Status:        {result.status.name}")
    print(f"Duration:      {result.duration_seconds:.2f}s")
    print()
    print(f"Total Jobs:   {result.total_jobs_found}")
    print(f"New Jobs:     {result.total_new_jobs}")
    print(f"Closed Jobs:  {result.total_closed_jobs}")
    print(f"Errors:       {result.total_errors}")
    print()

    if verbose and result.company_results:
        print("-" * 60)
        print("PER-COMPANY RESULTS")
        print("-" * 60)
        for cr in result.company_results:
            status_icon = {
                PipelineExitCode.SUCCESS: "[OK]",
                PipelineExitCode.PARTIAL: "[!!]",
                PipelineExitCode.FAILED: "[XX]",
            }.get(cr.status, "[??]")
            print(f"{status_icon} {cr.company_slug}")
            print(f"     Jobs Found:  {cr.jobs_found}")
            print(f"     New Jobs:    {cr.new_jobs}")
            print(f"     Closed:      {cr.closed_jobs}")
            print(f"     Duration:    {cr.duration_ms}ms")
            if cr.error_type:
                print(f"     Error:       {cr.error_type}: {cr.error_message}")
            if cr.warnings:
                for warning in cr.warnings:
                    print(f"     Warning:     {warning}")
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
    """Main entrypoint for the CLI.

    Returns:
        Exit code (0=success, 1=partial, 2=failed)
    """
    parser = argparse.ArgumentParser(
        prog="run_scrape",
        description="Scrape job listings from company career pages.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                     Scrape all active companies
  %(prog)s --company opswat    Scrape only opswat
  %(prog)s --dry-run           Test without database writes
  %(prog)s -v                  Verbose output

Exit codes:
  0 - SUCCESS: All companies scraped successfully
  1 - PARTIAL: Some companies had issues
  2 - FAILED: All companies failed or pipeline crashed
        """,
    )

    parser.add_argument(
        "-c",
        "--company",
        type=str,
        metavar="SLUG",
        help="Scrape only this company (by slug)",
    )

    parser.add_argument(
        "-d",
        "--dry-run",
        action="store_true",
        help="Run without database writes (testing only)",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose (debug) output",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    args = parser.parse_args()

    return asyncio.run(async_main(args))


if __name__ == "__main__":
    sys.exit(main())
