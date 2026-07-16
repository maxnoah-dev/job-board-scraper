# ADR 0006 — Scheduler & CSV export

- Status: Accepted
- Date: 2026-07-15
- Phase: 0 (Scope & Decisions)
- Authors: Tech Lead
- Supersedes: none

## Context

`TECHNICAL.md` §7 builds the system around `APScheduler` running on the same
container as the ETL pipeline. In practice we need the production deployment
to be driven by an external scheduler (cron, GitHub Actions, Argo, etc.) so
that retries, concurrency, and observability sit outside the application
container. We also need an export format that is reproducible and safe.

## Decision

### Scheduler

- Production runs as a **one-shot Docker container** that exits with one of
  `success` / `partial` / `failed` after a single ETL run. The external
  scheduler is responsible for cadence and retry.
- `APScheduler` is **optional** and only used for local single-process runs
  during development and demos. It reuses the same application service and
  run lock; it does not get its own code path.
- A run lock guarantees that only one ETL run is in flight at a time per
  database. Manual runs and scheduled runs go through the same lock so they
  cannot overlap.
- Orphan recovery: at startup, any `scrape_runs.status = 'running'` older
  than `RUN_TIMEOUT_SECONDS` is marked `interrupted` and its open
  `scrape_attempts` are marked `interrupted` as well.

### CSV export

- Default export is **CSV**, UTF-8, RFC 4180 quoting, deterministic column
  order, sorted by `(company_name, title, canonical_url)`.
- Export contains **only normalised columns**: `company_name`,
  `job_title`, `location`, `job_url`, `canonical_url`, `date_posted`,
  `status`, `first_seen_at`, `last_seen_at`. `raw_data` is never exported.
- Default filter: `status = 'open'`. An optional flag allows exporting all
  rows including closed history.
- Export is **atomic**: written to a temp file in the same directory and
  renamed into place. Partial files never appear at the destination path.
- Export is **byte-for-byte reproducible** for a given database snapshot; the
  Phase 8 export test asserts that property.

## Alternatives Considered

### Alternative 1: Long-running scheduler container

- Pros: One binary to deploy.
- Cons: Hides failures behind a stuck process, no built-in retry story,
  harder to scale horizontally.
- Why not: External scheduler is the standard pattern for one-shot ETL.

### Alternative 2: XLSX export

- Pros: Convenient for non-technical reviewers.
- Cons: Non-deterministic binary format, harder to diff in code review, and
  `PLAN.md` does not require it.
- Why not: Deferred to a later release.

### Alternative 3: JSON Lines instead of CSV

- Pros: Easier to consume programmatically.
- Cons: Not what business stakeholders asked for, harder to open in a
  spreadsheet.
- Why not: CSV is the contract.

## Consequences

- Positive: Production failure mode is simple (one container, one exit code).
  Export is reproducible and diff-friendly.
- Negative: Two ways to invoke the pipeline (CLI + APScheduler). Mitigation:
  both go through the same `RunService`.
- Risks: Orphan recovery is only as good as the database's clock. Mitigation:
  use `started_at` from the database, not the container clock.

## Open questions

- None at M0. The export schema is fixed; additional columns require an ADR.