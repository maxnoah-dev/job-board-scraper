# Alembic Migrations

This directory contains database migration scripts for the job-board-scraper project.

## Structure

```
migrations/
├── alembic.ini          # Alembic configuration
├── env.py               # Migration environment (async SQLAlchemy 2 support)
├── script.py.mako       # Template for new migrations
└── versions/            # Migration scripts
    └── 001_initial_schema.py  # Initial schema (companies, jobs, scrape_runs, scrape_attempts)
```

## Quick Start

### Apply Migrations

```bash
# Apply all migrations
alembic -c migrations/alembic.ini upgrade head

# Apply specific migration
alembic -c migrations/alembic.ini upgrade 001_initial_schema_a1b2c3d4
```

### Create New Migration

```bash
# Autogenerate migration from model changes
alembic -c migrations/alembic.ini revision --autogenerate -m "description"

# Create empty migration
alembic -c migrations/alembic.ini revision -m "description"
```

### Other Commands

```bash
# Show current migration
alembic -c migrations/alembic.ini current

# Show migration history
alembic -c migrations/alembic.ini history

# Rollback one migration
alembic -c migrations/alembic.ini downgrade -1

# Rollback all migrations
alembic -c migrations/alembic.ini downgrade base
```

## Database Configuration

The migration uses the `DATABASE_URL` environment variable. Default is SQLite:

```bash
# SQLite (default)
export DATABASE_URL="sqlite:///./data/jobs.db"

# PostgreSQL
export DATABASE_URL="postgresql+asyncpg://user:pass@host/db"
```

## Supported Databases

- **SQLite** (development) - Full support
- **PostgreSQL** (production) - Full support with JSONB storage

## Tables

1. **companies** - Job sources with adapter configuration
2. **jobs** - Job listings with deduplication on (company_id, canonical_url)
3. **scrape_runs** - ETL pipeline invocations
4. **scrape_attempts** - Per-company metrics within a scrape run
