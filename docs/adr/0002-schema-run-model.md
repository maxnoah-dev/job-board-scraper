# ADR 0002 — Schema & Run model

- Status: Accepted
- Date: 2026-07-15
- Phase: 0 (Scope & Decisions)
- Authors: Tech Lead
- Supersedes: none
- Related: ADR-0003 (job identity), ADR-0004 (stale closure)

## Context

`TECHNICAL.md` mixes a per-company `scrape_logs` table with an ERD that shows
`scrape_logs.job_id`, which is inconsistent. The semantics we need are:

- A top-level "run" covers a single invocation of the ETL pipeline.
- For each company attempted in that run we keep per-company metrics.
- Per-job appearance history is **not** required for the MVP and is not
  stored on `scrape_logs`.

## Decision

Adopt the following schema:

- `scrape_runs` — one row per pipeline invocation (manual or scheduled).
  Fields: `id`, `started_at`, `finished_at`, `status` (`running`,
  `success`, `partial`, `failed`, `cancelled`, `interrupted`),
  `triggered_by`, `notes`.
- `scrape_attempts` — one row per `(run, company)`. Fields: `id`,
  `run_id` (FK), `company_id` (FK), `started_at`, `finished_at`,
  `status`, `jobs_found`, `jobs_valid`, `records_rejected`, `new_jobs`,
  `closed_jobs`, `pages_fetched`, `requests_made`, `complete`,
  `authoritative_snapshot`, `error_type`, `error_message`, `warnings`.

No `job_id` column on `scrape_attempts`.

## Consequences

- Per-company isolation is explicit; concurrency/failure isolation works on
  `scrape_attempts`, not on `scrape_logs`.
- Orphan recovery: at startup any `scrape_runs.status = 'running'` older than
  the run timeout is set to `interrupted`, and its open `scrape_attempts`
  become `interrupted`.
- Future per-job observation history (if needed) lives in a separate
  `job_observations` table to avoid overloading `scrape_attempts`.

## Open questions

- None.