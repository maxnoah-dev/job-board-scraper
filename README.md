# job-board-scraper

Async ETL pipeline that scrapes job listings from 11+ company career pages and aggregates them into a single normalized database. Implemented in Python 3.11+ on top of `asyncio`, `httpx`, `pydantic`, and `SQLAlchemy 2`.

> **Status:** Phase 9 (Docker + PostgreSQL + CI hardening) complete. See [docs/ROADMAP.md](docs/ROADMAP.md) for the single source of truth on progress.

## Architecture

```
ORCHESTRATOR (external scheduler or APScheduler)
   │
   ▼
ETL PIPELINE
   EXTRACT (adapters) → TRANSFORM → DEDUPE → LOAD → REPORT
   │
   ▼
MONITORING (AlertManager + MetricsCollector)
```

Three adapter families:

| Family | Difficulty | Examples (current manifest) |
| --- | --- | --- |
| API/ATS | low | OPSWAT, Vancity (synthetic fixtures until approved) |
| HTML | medium | TechCorp, StartupXYZ (static page scraping) |
| Browser | high | TikTok, Northrop Grumman — **deferred for release 1** under [ADR-0007](docs/adr/0007-compliance.md) |

For the full architectural contract read [docs/TECHNICAL.md](docs/TECHNICAL.md), and for the phased plan read [docs/ROADMAP.md](docs/ROADMAP.md).

## Repository layout

```
job-board-scraper/
├── pyproject.toml        # Poetry metadata + tool config (ruff, pyright, pytest, coverage)
├── Dockerfile            # Multi-stage image: builder → runtime → runtime-browser
├── docker-compose.yml    # Local dev stack (PostgreSQL + scraper)
├── README.md             # This file
├── .env.example          # Placeholder-only environment template
├── docs/                 # PLAN.md, TECHNICAL.md, ROADMAP.md, ADRs, source manifest
├── src/                  # Application source
├── tests/                # Unit + integration + e2e tests
├── scripts/              # Operational scripts (init_db, seed_companies, run_scrape)
├── migrations/           # Alembic schema migrations
├── config/              # Per-adapter configs
├── data/                 # SQLite database + CSV reports
└── logs/                 # Structured log output
```

## Tooling

| Tool | Purpose |
| --- | --- |
| Python 3.11+ | Runtime |
| Poetry | Dependency management and lockfile |
| Pydantic 2 / pydantic-settings 2 | Settings + domain contracts |
| pytest + pytest-asyncio + pytest-cov | Test runner |
| Ruff | Linter and formatter |
| Pyright | Static type checker |
| detect-secrets | Secret scanner |

## Quickstart (local development)

These steps assume Python 3.11+ is on the path.

```powershell
# 1. Create the local virtual environment (already done if .venv exists).
python -m venv .venv

# 2. Install runtime + dev dependencies.
.venv\Scripts\python.exe -m pip install -e ".[dev]"

# 3. Initialize the database (idempotent — safe to re-run).
.venv\Scripts\python.exe scripts\init_db.py

# 4. Seed company records from the source manifest (idempotent).
.venv\Scripts\python.exe scripts\seed_companies.py

# 5. Run the scraper (all companies, dry-run first).
.venv\Scripts\python.exe scripts\run_scrape.py --dry-run
.venv\Scripts\python.exe scripts\run_scrape.py

# 6. Run the test suite.
.venv\Scripts\python.exe -m pytest

# 7. Run the lint / format / type checks.
.venv\Scripts\python.exe -m ruff format .
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m pyright src tests
```

If `.\.venv\Scripts\python.exe` is on `PATH` instead, drop the prefix in the snippets above.

## Docker (recommended for production)

The production runtime is a **one-shot container** driven by an external scheduler (Kubernetes CronJob, Cloud Scheduler, etc.) per [ADR-0006](docs/adr/0006-scheduler-export.md).

### Build the image

```bash
# Standard image (no browser automation)
docker build --target runtime -t job-board-scraper:latest .

# Image with Playwright + Chromium (only needed when browser sources are approved)
docker build --target runtime-browser -t job-board-scraper:browser .
```

### Run with docker-compose (local PostgreSQL)

```bash
# Start PostgreSQL and run the scraper against it
docker compose up --build postgres scraper

# Run a single scrape with dry-run
docker compose run --rm scraper python -m job_board_scraper.cli run --dry-run

# Run a specific company
docker compose run --rm scraper python -m job_board_scraper.cli run -c opswat

# Initialize the database
docker compose run --rm scraper python -m job_board_scraper.cli init-db

# Seed companies
docker compose run --rm scraper python -m job_board_scraper.cli seed

# Export jobs to CSV
docker compose run --rm scraper python -m job_board_scraper.cli export -o /app/data/jobs.csv

# Shell into the container
docker compose run --rm --entrypoint bash scraper
```

### Run standalone (external PostgreSQL)

```bash
# Set environment
export DATABASE_URL="postgresql+asyncpg://jobs:password@host:5432/jobs"
export LOG_LEVEL="INFO"

# Run
docker run --rm \
  -e DATABASE_URL \
  -e LOG_LEVEL \
  -v ./data:/app/data \
  -v ./logs:/app/logs \
  job-board-scraper:latest \
  python -m job_board_scraper.cli run
```

### Environment variables

| Variable | Default | Description |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/jobs.db` | Async database DSN |
| `LOG_LEVEL` | `INFO` | Minimum log level |
| `LOG_FILE` | `./logs/scraper.log` | Log file path |
| `SCHEDULER_ENABLED` | `false` | Enable APScheduler (local only) |
| `PLAYWRIGHT_BROWSERS_INSTALLED` | `false` | Set true when using browser target |
| `ALERT_EMAIL_ENABLED` | `false` | Enable email alerting |
| `ALERT_SLACK_WEBHOOK` | (empty) | Slack webhook URL |
| `EXPORT_DIR` | `./data` | CSV export directory |

## CLI Reference

The CLI supports subcommands:

```bash
# Run scrape
job-board-scraper run              # All active companies
job-board-scraper run -c opswat   # Single company
job-board-scraper run --dry-run   # No database writes

# Database
job-board-scraper init-db         # Create tables
job-board-scraper seed            # Seed companies

# Export
job-board-scraper export          # Export open jobs to CSV
job-board-scraper export --all    # Include closed jobs
```

Exit codes: `0` = success, `1` = partial, `2` = failed

## Configuration

Configuration is environment-driven; no secrets are committed to the repo. See [`.env.example`](.env.example) for the full placeholder template. Real values come from the operator's environment variable store (Kubernetes Secret, AWS Secrets Manager, GitHub Actions secret, etc.).

## Deployment options

| Target | How | Notes |
| --- | --- | --- |
| Local / dev | Python direct + SQLite | `python scripts/run_scrape.py` |
| Local / prod-like | docker compose + PostgreSQL | `docker compose up scraper` |
| Cloud / production | One-shot container + external scheduler | See ADR-0006 |
| CI / tests | GitHub Actions matrix | PostgreSQL service in `.github/workflows/ci.yml` |

## Compliance and source policy

We do not bypass access controls, solve CAPTCHAs, or rotate residential proxies. Each of the 11 sources listed in [docs/sources/manifest.md](docs/sources/manifest.md) has a written decision in [docs/sources/compliance-notes.md](docs/sources/compliance-notes.md). Sources whose compliance status is not `approved` are loaded with `is_active: false` and cannot be enabled without a new ADR.

## License

Proprietary — internal use only.
