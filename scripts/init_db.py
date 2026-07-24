"""Idempotent database initialization script.

Creates all tables and runs pending Alembic migrations so the schema
matches what the application expects. Safe to re-run â€” repeated calls
are no-ops after the first successful run.

Exit codes:
    0 - SUCCESS (tables created / already up-to-date)
    1 - FAILED (error)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Ensure src is on the path so we can import the package.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from job_board_scraper.core.database import check_connection, close_db, init_db

LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
LOG_FILE = LOG_DIR / "init_db.log"


def setup_logging(verbose: bool = False) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        level=level,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(LOG_FILE, mode="a"),
        ],
    )


async def async_main(verbose: bool) -> int:
    setup_logging(verbose)
    logger = logging.getLogger(__name__)

    logger.info("Starting database initialization")
    print("=" * 60)
    print("DATABASE INITIALIZATION")
    print("=" * 60)

    try:
        if not await check_connection():
            logger.error("Cannot connect to database. Check DATABASE_URL.")
            print("ERROR: Cannot connect to database.")
            print("Set DATABASE_URL to a valid async connection string.")
            return 1

        await init_db()
        logger.info("Database tables created / already up-to-date")

        print()
        print("Database initialized successfully.")
        print("Tables created: companies, jobs, scrape_runs, scrape_attempts")
        print("=" * 60)
        return 0

    except Exception:
        logger.exception("Database initialization failed")
        print()
        print("ERROR: Initialization failed. Check logs for details.")
        print(f"Log file: {LOG_FILE}")
        return 1
    finally:
        await close_db()


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="init-db",
        description="Initialize the job-board-scraper database (idempotent).",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()
    return asyncio.run(async_main(args.verbose))


if __name__ == "__main__":
    sys.exit(main())
