"""Idempotent company seeding script.

Inserts or updates company records from the approved source manifest.
Only seeds sources whose compliance_status is "approved" or
"needs-review" (fixture-only). Skips "blocked-*", "cancelled",
and unknown slugs.

The script is safe to re-run â€” existing companies are refreshed, not
duplicated (upsert on slug).

Exit codes:
    0 - SUCCESS
    1 - FAILED
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from job_board_scraper.core.database import check_connection, close_db, init_db
from job_board_scraper.models.db_company import AdapterType, Company

LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
LOG_FILE = LOG_DIR / "seed_companies.log"

# Seed data derived from docs/sources/manifest.md.
# Only sources that are "approved" or "needs-review" (fixture-only) are seeded.
# Browser sources (blocked-by-policy) and owner-pending sources are skipped.
_SEED_COMPANIES: list[dict] = [
    {
        "name": "OPSWAT",
        "slug": "opswat",
        "adapter_type": AdapterType.API.value,
        "base_url": "https://www.opswat.com/careers",
        "config": {},
        "is_active": True,
        "authoritative": True,
        "compliance_status": "needs-review",
    },
    {
        "name": "Vancity",
        "slug": "vancity",
        "adapter_type": AdapterType.API.value,
        "base_url": "https://jobs.vancity.com",
        "config": {},
        "is_active": True,
        "authoritative": True,
        "compliance_status": "needs-review",
    },
    {
        "name": "TechCorp",
        "slug": "techcorp",
        "adapter_type": AdapterType.HTML.value,
        "base_url": "https://example.com/careers",
        "config": {
            "selectors": {"job_list": ".job-listing", "title": "h2", "url": "a"}
        },
        "is_active": True,
        "authoritative": True,
        "compliance_status": "needs-review",
    },
    {
        "name": "StartupXYZ",
        "slug": "startup-xyz",
        "adapter_type": AdapterType.HTML.value,
        "base_url": "https://startup.example.com/jobs",
        "config": {},
        "is_active": False,
        "authoritative": True,
        "compliance_status": "needs-review",
    },
    {
        "name": "TikTok",
        "slug": "tiktok",
        "adapter_type": AdapterType.BROWSER.value,
        "base_url": "https://careers.tiktok.com",
        "config": {},
        "is_active": False,
        "authoritative": True,
        "compliance_status": "blocked-by-policy",
    },
    {
        "name": "Northrop Grumman",
        "slug": "northrop",
        "adapter_type": AdapterType.BROWSER.value,
        "base_url": "https://www.northropgrumman.com/careers",
        "config": {},
        "is_active": False,
        "authoritative": True,
        "compliance_status": "blocked-by-policy",
    },
]


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


async def _upsert_company(session, data: dict) -> tuple[bool, str]:
    """Insert or update a company. Returns (was_created, slug)."""
    from sqlalchemy import select

    slug = data["slug"]
    # Strip non-column fields (manifest annotations only).
    db_data = {k: v for k, v in data.items() if k not in ("id", "compliance_status")}

    stmt = select(Company).where(Company.slug == slug)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        for key, value in db_data.items():
            setattr(existing, key, value)
        await session.flush()
        return False, slug

    company = Company(**db_data)
    session.add(company)
    await session.flush()
    return True, slug


async def async_main(verbose: bool, force: bool = False) -> int:
    setup_logging(verbose)
    logger = logging.getLogger(__name__)

    logger.info("Starting company seeding")
    print("=" * 60)
    print("COMPANY SEEDING")
    print("=" * 60)

    try:
        if not await check_connection():
            logger.error("Cannot connect to database.")
            print("ERROR: Cannot connect to database.")
            return 1

        await init_db()

        from job_board_scraper.core.database import session_scope

        created: list[str] = []
        updated: list[str] = []
        skipped: list[str] = []

        for data in _SEED_COMPANIES:
            slug = data["slug"]
            status = data.get("compliance_status", "unknown")

            # Skip sources that are not yet approved or needs-review.
            if status not in ("approved", "needs-review"):
                skipped.append(f"{slug} (compliance: {status})")
                logger.debug("Skipping %s: compliance_status=%s", slug, status)
                continue

            async with session_scope() as session:
                was_created, seeded_slug = await _upsert_company(session, data)
                if was_created:
                    created.append(seeded_slug)
                else:
                    updated.append(seeded_slug)

        print()
        if created:
            print(f"Created:    {', '.join(created)}")
        if updated:
            print(f"Updated:    {', '.join(updated)}")
        if skipped:
            print(f"Skipped:    {', '.join(skipped)}")
        print()
        print(
            f"Total: {len(created)} created, {len(updated)} updated, {len(skipped)} skipped"
        )
        print("=" * 60)
        return 0

    except Exception:
        logger.exception("Company seeding failed")
        print()
        print("ERROR: Seeding failed. Check logs for details.")
        return 1
    finally:
        await close_db()


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="seed-companies",
        description="Seed company records from the source manifest (idempotent).",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-activation of currently inactive companies",
    )
    args = parser.parse_args()
    return asyncio.run(async_main(args.verbose, args.force))


if __name__ == "__main__":
    sys.exit(main())
