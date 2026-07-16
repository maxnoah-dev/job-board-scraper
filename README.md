# job-board-scraper

Async ETL pipeline that scrapes job listings from 11+ company career pages and aggregates them into a single normalized database. Implemented in Python 3.11+ on top of `asyncio`, `httpx`, `pydantic`, and `SQLAlchemy 2`.

> **Status:** Project scaffold — Phase 1 (foundation + quality tooling) is the current workstream. See [docs/ROADMAP.md](docs/ROADMAP.md) for the single source of truth on progress, blockers, and decisions.

## Architecture

```
ORCHESTRATOR (APScheduler / external scheduler)
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
| API/ATS | low | OPSWAT, Vancity (synthetic fixtures in Phase 4) |
| HTML | medium | placeholder — see [docs/sources/manifest.md](docs/sources/manifest.md) |
| Browser | high | TikTok, Northrop Grumman — **deferred for release 1** under [ADR-0007](docs/adr/0007-compliance.md) |

For the full architectural contract read [docs/TECHNICAL.md](docs/TECHNICAL.md), and for the phased plan read [docs/ROADMAP.md](docs/ROADMAP.md).

## Repository layout

```
job-board-scraper/
├── pyproject.toml        # Poetry metadata + tool config (ruff, pyright, pytest, coverage)
├── README.md             # This file
├── .env.example          # Placeholder-only environment template
├── docs/                 # PLAN.md, TECHNICAL.md, ROADMAP.md, ADRs, source manifest
├── src/                  # Application source (added in Phase 1.2)
├── tests/                # Unit + integration + e2e tests
├── scripts/              # Operational scripts (init_db, seed_companies, run_scrape)
├── config/               # settings.yaml + per-adapter configs
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
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

# 3. Run the test suite.
.\.venv\Scripts\python.exe -m pytest

# 4. Run the lint / format / type checks.
.\.venv\Scripts\python.exe -m ruff format .
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pyright src tests
```

If `.\.venv\Scripts\python.exe` is on `PATH` instead, drop the prefix in the snippets above.

## Configuration

Configuration is environment-driven; no secrets are committed to the repo. See [`.env.example`](.env.example) for the placeholder template. Real values come from the operator's environment variable store (Kubernetes Secret, AWS Secrets Manager, GitHub Actions secret, etc.).

## Compliance and source policy

We do not bypass access controls, solve CAPTCHAs, or rotate residential proxies. Each of the 11 sources listed in [docs/sources/manifest.md](docs/sources/manifest.md) has a written decision in [docs/sources/compliance-notes.md](docs/sources/compliance-notes.md). Sources whose compliance status is not `approved` are loaded with `enabled: false` and cannot be enabled without a new ADR.

## License

Proprietary — internal use only.
