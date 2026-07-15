# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**job-board-scraper** is a Python-based ETL pipeline that scrapes job listings from 11+ company career pages and aggregates them into a normalized database. It supports three adapter types: API integrations, HTML scraping, and browser automation (for anti-bot sites).

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11+ |
| Async Runtime | asyncio + aiohttp |
| Web Scraping | httpx, beautifulsoup4, playwright |
| Data Validation | Pydantic |
| Database | SQLite (dev) / PostgreSQL (prod), SQLAlchemy + aiosqlite |
| Scheduler | APScheduler |
| Testing | pytest + pytest-asyncio |
| Package Manager | Poetry |
| Formatting | Black, Ruff |

## Architecture

The system follows an **ETL Pipeline** pattern with an **Adapter/Plugin Architecture**:

```
ORCHESTRATOR (APScheduler + Event Loop)
    |
    v
EXTRACT (11 Adapters) -> TRANSFORM (Normalize + Validate) -> DEDUPE (Job_URL unique) -> LOAD (Database + Report)
    |
    v
MONITORING (Error Tracker + Alert Manager + Metrics Collector)
```

### Adapter Protocol Types

- **API Adapter**: API/ATS integrations (easiest)
- **HTML Adapter**: Static HTML scraping (medium)
- **Browser Adapter**: Anti-bot sites requiring Playwright (hardest)

### Key Design Patterns

- **Adapter Pattern** (Plugin System): Each company gets its own adapter implementing `BaseAdapter`
- **Strategy Pattern** (Transformer): Each adapter can have a custom transformer strategy
- **Observer Pattern** (Monitoring): Alert subscribers receive events
- **Repository Pattern** (Data Access): Abstraction layer between business logic and database

## Directory Structure

```
job-board-scraper/
├── src/
│   ├── core/           # Config, database, logging
│   ├── etl/            # Base ETL, extractor, transformer, loader, deduplicator
│   ├── adapters/       # Plugin system (base, registry, protocols, implementations)
│   ├── models/          # Pydantic + SQLAlchemy schemas
│   ├── scheduler/      # APScheduler setup
│   ├── monitoring/      # Alert manager, metrics, detectors
│   └── utils/           # Rate limiter, retry logic, user agents
├── tests/               # Unit, integration, E2E tests + fixtures
├── scripts/             # init_db, seed_companies, run_scrape
├── config/              # settings.yaml + per-adapter configs
├── docs/                # PLAN.md, TECHNICAL.md
├── logs/                # Application logs
└── data/                # Export files (CSV, Excel)
```

## Database Schema

- **companies**: id, name, slug, adapter_type, base_url, config (JSON), is_active
- **jobs**: id, company_id, title, location, job_url (UNIQUE), date_posted, status, raw_data (JSON)
- **scrape_logs**: id, company_id, started_at, completed_at, status, jobs_found, new_jobs, closed_jobs, error_message, duration_ms

## Key Commands

```bash
# Install dependencies
poetry install

# Initialize database
python scripts/init_db.py

# Seed company data
python scripts/seed_companies.py

# Run a manual scrape
python scripts/run_scrape.py

# Run tests
pytest tests/ -v --cov=src --cov-report=term-missing
```

## Concurrency Model

- `asyncio.gather()` runs all adapters concurrently
- Semaphore limit = 5 to prevent overwhelming target servers
- Per-adapter rate limiting: API (0.5-1s), HTML (2-4s), Browser (3-6s)

## Error Handling Strategy

| Category | Recovery Strategy |
|----------|------------------|
| Transient (timeout) | Retry 3x with exponential backoff |
| Parse Error | Log warning, skip item, continue |
| Authentication (401/403) | Alert admin, disable adapter |
| Anti-Bot (Cloudflare) | Switch to browser mode, alert admin |
| Data Quality (0 jobs) | Alert admin immediately |

## Security Guidelines

- Rate limiting to respect target servers and prevent IP bans
- User-agent rotation to mimic real browsers
- Credentials stored in environment variables, never hardcoded
- No PII storage beyond job URLs
- All external responses validated

## Development Workflow

1. **Plan**: Use `/plan` for complex features
2. **TDD**: Use `/tdd` — write tests first, then implementation
3. **Review**: Use `/code-review` after writing code
4. **Commit**: Conventional commits (`feat:`, `fix:`, `refactor:`, etc.)

## Alerting

- **Email**: Critical failures, 0 jobs alert
- **Slack**: Real-time status updates
- **Log file**: All events for debugging

## Deployment Options

- **Local**: `python -m src.scheduler` (cron job)
- **Docker**: Containerized deployment
- **Cloud**: AWS Lambda, Google Cloud Run, Railway/Render
