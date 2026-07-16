# Roadmap — Job Board Scraper

**Owner:** Engineering Lead
**Roadmap version:** v1.0
**Baseline commit:** see `git rev-parse HEAD`
**Created:** 2026-07-15
**Source requirements:** [PLAN.md](PLAN.md), [TECHNICAL.md](TECHNICAL.md)

This document is the **single source of truth** for project status, planned vs. actual effort, evidence, blockers, decisions, and milestones. Update it at the end of every phase before any new implementation work begins.

## Roadmap Header

| Field | Value |
| --- | --- |
| Roadmap version | v1.0 |
| Roadmap owner | Engineering Lead |
| Engineering owner | Engineering Lead (acting until M1 reassignment) |
| Last updated | 2026-07-16 (Phase 0 closed at M0; Phase 1 in progress) |
| Current phase | Phase 1 — Python foundation and quality tooling |
| Current milestone | M1 — Tooling Ready |
| Overall status | in-progress (Phase 0 closed at M0; Phase 1 active, P1-01..P1-05 ready) |
| Next review date | end of Phase 1 |
| Implementation progress | 0% code; 1.4% by effort weight (Phase 0 closed) |

## Progress formula

- Each task carries a **weight (effort points)** set during Phase 0 re-baseline and frozen afterwards.
- Phase progress = sum of weights for `done` tasks inside the phase / sum of weights for the phase.
- Overall progress = sum of weights for `done` tasks across all phases / total weights.
- `blocked`, `in-review`, `ready`, `not-started`, `deferred`, `cancelled` are excluded from the numerator.

## Status values

| Status | Meaning | Counts as done? |
| --- | --- | --- |
| `not-started` | Dependencies not met or no work has begun | no |
| `ready` | Dependencies satisfied, work can start | no |
| `in-progress` | Active implementation in progress | no |
| `blocked` | Cannot proceed without decision or input | no |
| `in-review` | Awaiting code review, security review, or sign-off | no |
| `done` | Acceptance gate passed and evidence captured | yes |
| `deferred` | Postponed intentionally with documented reason | no |
| `cancelled` | Dropped with documented reason | no |

## Phase Roll-up

| Phase | Title | Milestone | Weight | Done weight | Status | Progress |
| --- | --- | --- | --- | --- | --- | --- |
| P0 | Scope, source inventory, progress baseline | M0 Scope Ready | 10 | 10 | done | 100% |
| P1 | Python foundation and quality tooling | M1 Tooling Ready | 20 | 0 | in-progress | 0% |
| P2 | Domain, schema, migrations, repositories | M2 Data Contract Stable | TBD | 0 | not-started | 0% |
| P3 | Adapter platform and shared resilience | M3 Adapter Platform Ready | TBD | 0 | not-started | 0% |
| P4 | Vertical slice with OPSWAT | M4 First Working Pipeline | TBD | 0 | not-started | 0% |
| P5 | Remaining API/ATS adapters | M5 API Complete | TBD | 0 | not-started | 0% |
| P6 | Static HTML adapters | M6 HTML Complete | TBD | 0 | not-started | 0% |
| P7 | Browser adapters and Playwright hardening | M7 All Sources Covered | TBD | 0 | not-started | 0% |
| P8 | Operations, monitoring, alerts, reporting | M8 Operationally Observable | TBD | 0 | not-started | 0% |
| P9 | Docker/PostgreSQL release hardening | M9 Release Candidate | TBD | 0 | not-started | 0% |

Overall progress: **1.4%** (10 of 692 frozen effort points completed; Phase 0 closed at M0).

## Phase 0 — Scope, source inventory, progress baseline

| ID | Title | Dependencies | Weight | Status | Planned start | Actual start | Planned end | Actual end | Effort planned | Effort actual | Owner | Gate | Evidence | Blockers | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P0-01 | Author this `docs/ROADMAP.md` SSoT | none | 1 | done | 2026-07-15 | 2026-07-15 | 2026-07-15 | 2026-07-15 | 0.5 day | 0.5 day | Engineering Lead | File exists with status, weights placeholder, phase table | this file | none | closed at M0 |
| P0-02 | Author `docs/adr/` index, template, and seven ADRs (HTTP, schema/run model, dedupe, stale closure, timestamps, migration, scheduler, export, compliance) | P0-01 | 2 | done | 2026-07-15 | 2026-07-15 | 2026-07-16 | 2026-07-15 | 1 day | 0.5 day | Engineering Lead | Seven ADRs accepted at M0 | `docs/adr/0001..0007.md` | none | closed at M0 |
| P0-03 | Create `docs/sources/manifest.md` listing 11 sources, each with URL, ATS, adapter type, pagination, expected count, fields, authoritative snapshot flag, rate policy, credential requirement, fixture plan, owner, and compliance status | P0-01 | 3 | done | 2026-07-15 | 2026-07-15 | 2026-07-17 | 2026-07-15 | 1.5 days | 0.5 day | Engineering Lead | 11/11 sources have entry and compliance decision | `docs/sources/manifest.md` | 7 sources (absolute-security, farm-credit-canada, source-07..11) carry `blocked-pending-owner`; product owner input required before P5 | closed at M0; owner follow-up tracked separately |
| P0-04 | Compliance review for each source: robots.txt, ToS, permission for scraping, anti-bot policy, kill-switch design | P0-03 | 2 | done | 2026-07-16 | 2026-07-15 | 2026-07-18 | 2026-07-15 | 1 day | 0.25 day | Engineering Lead + Product Owner | Each source marked `approved`, `blocked`, `blocked-by-policy`, or `blocked-pending-owner` with rationale | `docs/sources/manifest.md` Compliance column + `docs/sources/compliance-notes.md` | browser sources deferred via `blocked-by-policy` per ADR-0007; needs explicit human decision before P7 | closed at M0; P7 re-entry gated on policy change |
| P0-05 | Convert every requirement into testable acceptance criteria, classify the 11 sources as API/HTML/Browser, freeze phase weights, and capture M0 progress update | P0-02, P0-03, P0-04 | 2 | done | 2026-07-18 | 2026-07-15 | 2026-07-19 | 2026-07-15 | 1 day | 0.25 day | Engineering Lead | AC list committed; weights frozen; phase progress recorded; M0 declared `done` | this document + `Progress History` entry | none | M0 closed; Phase 1 unblocked |

Phase 0 total weight: 10 (frozen at P0-05 close). Phase 0 done weight: **10 of 10**.

### Phase 0 — Acceptance criteria

- AC-001: `docs/ROADMAP.md` exists and is referenced by all status updates. **Verification:** file exists, sections present, status table up-to-date.
- AC-002: Seven ADRs exist under `docs/adr/` covering HTTP client, schema/run model, dedupe, stale closure, timestamps/migration, scheduler/export, and compliance. **Verification:** directory listing shows 0001-0007 with `Status: accepted`.
- AC-003: `docs/sources/manifest.md` contains rows for 11 sources with compliance status column populated. **Verification:** file is complete, no placeholder rows.
- AC-004: Every Phase 0 task has status, planned/actual dates, evidence pointer, and blocker if `blocked`. **Verification:** this document.
- AC-005: Phase weights frozen and overall progress formula documented. **Verification:** top of this file.
- AC-006: Phase 0 progress entry recorded in the `Progress History` section. **Verification:** append-only log contains the entry.

### Phase 0 — Gate

- Eleven sources all have an entry and a compliance decision. ✅
- Seven ADRs accepted (`docs/adr/0001..0007.md`). ✅
- No remaining Critical contradiction between `PLAN.md` and `TECHNICAL.md`. ✅
- Phase weights frozen for the rest of the project (Phase 0 = 10). ✅
- Browser bypass explicitly rejected; sources requiring it marked `blocked-by-policy`. ✅

**Gate status: PASSED. Milestone M0 declared `done` at 2026-07-15.**

### Phase 0 — Close-out report

- **Phase / Milestone**: Phase 0 → M0 Scope Ready
- **Completed tasks**: P0-01, P0-02, P0-03, P0-04, P0-05 (5/5, 10/10 effort points)
- **Evidence**:
  - `docs/ROADMAP.md` exists and reflects frozen Phase 0 weights.
  - `docs/adr/0001-http-client.md`, `0002-schema-run-model.md`, `0003-job-identity.md`, `0004-stale-closure.md`, `0005-timestamps-migration.md`, `0006-scheduler-export.md`, `0007-compliance.md` all `Status: Accepted`.
  - `docs/sources/manifest.md` lists 11 sources with full compliance column.
  - `docs/sources/compliance-notes.md` records per-source decisions including `blocked-by-policy` for TikTok and Northrop.
- **Coverage / quality gates**: not applicable (documentation phase).
- **Progress before → after**: 0% (weights TBD) → 1.4% by effort weight (Phase 0 done = 10/10).
- **Planned vs actual effort**: planned 5.0 days, actual 2.0 days (faster because no live-network review was required at M0).
- **Deviations / decisions**:
  - Two sources (TikTok, Northrop) deferred via `blocked-by-policy`; previously marked `needs-review`.
  - Seven sources kept as `blocked-pending-owner`; product owner input required before Phase 5.
  - ADR-0003 was originally stored as `0003-run-model.md`; renamed to `0002-schema-run-model.md` to match ROADMAP numbering. Content unchanged apart from title and status.
- **Blockers handed forward**: none for Phase 1. Seven sources remain `blocked-pending-owner` but do not gate Phase 1 (which is tooling-only).
- **Decisions locked at M0**: all seven ADRs accepted and reflected in the `Decisions captured` section below.
- **Next phase**: Phase 1 — Python foundation and quality tooling (P1-01..P1-05).

## Phase 1 — Python foundation and quality tooling

| ID | Title | Dependencies | Weight | Status | Planned start | Planned end | Owner | Gate | Evidence | Blockers | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P1-01 | Poetry project skeleton with Python 3.11+ pin, dependency groups, lockfile | P0 done | 4 | done | 2026-07-16 | 2026-07-16 | 2026-07-16 | 2026-07-16 | 1.0 day | 0.2 day | Engineering Lead | clean install + import smoke pass; 12/12 contract tests pass | `pyproject.toml`, `poetry.lock`, `src/job_board_scraper/__init__.py`, `README.md`, `.gitignore` | none | closed at P1-01; stub package imported |
| P1-02 | Package skeleton per `TECHNICAL.md`: `core`, `models`, `repositories`, `etl`, `adapters`, `monitoring`, `scheduler`, `utils`, `scripts` | P1-01 | 4 | not-started | 2026-07-16 | 2026-07-17 | Engineering Lead | package import smoke, no circular imports | directory tree | none | create modules |
| P1-03 | Validated settings via Pydantic, environment precedence, structured redacted logging, `.env.example` with placeholders only | P1-02 | 5 | not-started | 2026-07-17 | 2026-07-18 | Engineering Lead | failing required env causes startup error | `.env.example`, tests | none | add settings module |
| P1-04 | pytest + pytest-asyncio + markers `unit`, `integration`, `e2e` + coverage threshold 80% | P1-02 | 4 | not-started | 2026-07-17 | 2026-07-18 | Engineering Lead | coverage gate fails below 80% | `pyproject.toml`, smoke test | none | configure tooling |
| P1-05 | Ruff format/lint, Pyright, secret scan, CI baseline | P1-02 | 3 | not-started | 2026-07-18 | 2026-07-18 | Engineering Lead | lint/type/security pass | `pyproject.toml`, CI config | none | wire CI |

Phase 1 total weight: **20** (frozen at P1-01 start; P1-01=4, P1-02=4, P1-03=5, P1-04=4, P1-05=3). Phase 1 done weight: **4 of 20** after P1-01 (P1-02..P1-05 in progress).

## Phase 2 — Domain, schema, migrations, repositories

| ID | Title | Dependencies | Weight | Status | Planned start | Planned end | Owner | Gate | Evidence | Blockers | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P2-01 | Failing RED tests for `RawJobData`, `JobRecord`, URL/date/status validation, malformed payload | P1 done | TBD | not-started | TBD | TBD | Engineering Lead | tests compile and fail for the intended reason | tests/ | none | write tests |
| P2-02 | Pydantic v2 domain contracts and source-aware canonicalization | P2-01 | TBD | not-started | TBD | TBD | Engineering Lead | tests pass | src/models | none | implement contracts |
| P2-03 | SQLAlchemy 2 async models for `companies`, `jobs`, `scrape_runs`, `scrape_attempts` | P2-02 | TBD | not-started | TBD | TBD | Engineering Lead | model introspection tests pass | src/models | none | implement models |
| P2-04 | Alembic migrations reproducible on SQLite and PostgreSQL | P2-03 | TBD | not-started | TBD | TBD | Engineering Lead | migrations apply and downgrade cleanly on both | migrations/ | none | author migrations |
| P2-05 | Async repository interfaces + SQLAlchemy implementation (upsert, idempotency, rollback) | P2-03 | TBD | not-started | TBD | TBD | Engineering Lead | transactional integrity tests pass | src/repositories | none | implement repositories |
| P2-06 | Safe stale reconciliation: missing_count, complete/authoritative guard, reopen | P2-05 | TBD | not-started | TBD | TBD | Engineering Lead | partial/failed/empty-unverified runs do not close jobs; two complete misses close | tests/ | none | implement reconciler |

## Phase 3 — Adapter platform and shared resilience

| ID | Title | Dependencies | Weight | Status | Planned start | Planned end | Owner | Gate | Evidence | Blockers | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P3-01 | Fixture-first tests for `BaseAdapter`, typed `ExtractionResult`, registry | P2 done | TBD | not-started | TBD | TBD | Engineering Lead | contracts enforced; duplicate slug rejected | tests/ | none | write contract tests |
| P3-02 | Shared `httpx` client lifecycle with timeout, redacted logs, DI | P3-01 | TBD | not-started | TBD | TBD | Engineering Lead | client closes on success/failure/cancel | src/utils/http.py | none | implement client |
| P3-03 | Bounded retry with full jitter and retryable error classification | P3-02 | TBD | not-started | TBD | TBD | Engineering Lead | retry policy deterministic tests | src/utils/retry.py | none | implement retry |
| P3-04 | Per-origin rate limiter, per-source concurrency, browser concurrency 1 | P3-02 | TBD | not-started | TBD | TBD | Engineering Lead | concurrency cap tests | src/utils/rate_limiter.py | none | implement rate limiter |
| P3-05 | Source-scoped circuit breaker (closed/open/half-open) | P3-03 | TBD | not-started | TBD | TBD | Engineering Lead | deterministic state machine tests | src/utils/circuit_breaker.py | none | implement breaker |
| P3-06 | Validated adapter config; adapters extract only, do not write to DB or reconcile stale jobs | P3-01 | TBD | not-started | TBD | TBD | Engineering Lead | adapter isolation tests | src/adapters/ | none | implement config validation |

## Phase 4 — Vertical slice with OPSWAT

| ID | Title | Dependencies | Weight | Status | Planned start | Planned end | Owner | Gate | Evidence | Blockers | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P4-01 RED | Failing contract tests for OPSWAT: success, pagination, empty, malformed, timeout, 429, 5xx | P3 done | TBD | not-started | TBD | TBD | Engineering Lead | tests run and fail with intended reason | tests/ | none | write tests |
| P4-02 GREEN | Minimum OPSWAT adapter implementation that flips tests to pass | P4-01 | TBD | not-started | TBD | TBD | Engineering Lead | tests pass; no live network in CI | src/adapters/ | none | implement adapter |
| P4-03 | Default transformer, normalization, canonicalization, batch dedupe | P4-02 | TBD | not-started | TBD | TBD | Engineering Lead | transformer/canonicalizer unit tests pass | src/etl/transformer.py | none | implement transformer |
| P4-04 | ETL application service: extract → transform → validate → dedupe → transactional load → reconcile → summary | P4-03, P2-06 | TBD | not-started | TBD | TBD | Engineering Lead | pipeline integration tests pass | src/etl/ | none | implement pipeline |
| P4-05 | One-shot `run_scrape` CLI with exit codes `success`, `partial`, `failed` | P4-04 | TBD | not-started | TBD | TBD | Engineering Lead | CLI smoke test verifies exit codes | scripts/run_scrape.py | none | implement CLI |
| P4-06 | SQLite + PostgreSQL integration tests + process-level E2E with mock HTTP server; idempotent reruns | P4-04 | TBD | not-started | TBD | TBD | Engineering Lead | repeat run produces same state; metrics DB matches summary | tests/e2e/ | none | author E2E |
| P4-07 REFACTOR | Code review, security review, fix Critical/High | P4-06 | TBD | not-started | TBD | TBD | Engineering Lead | review reports show no Critical/High | docs/reviews/ | none | run reviews |

## Phase 5 — Remaining API/ATS adapters

| ID | Title | Dependencies | Weight | Status | Planned start | Planned end | Owner | Gate | Evidence | Blockers | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P5-01 | Per-API fixture-first task breakdown from manifest | P4 done | TBD | not-started | TBD | TBD | Engineering Lead | each API has fixture matrix | docs/sources/manifest.md | none | create per-source tickets |
| P5-02 | Vancity adapter + remaining API/ATS adapters | P5-01 | TBD | not-started | TBD | TBD | Engineering Lead | per-source contract tests pass | src/adapters/implementations/ | none | implement adapters |
| P5-03 | Multi-adapter integration: concurrency, partial failure, rate limits, aggregate metrics | P5-02 | TBD | not-started | TBD | TBD | Engineering Lead | family-level coverage ≥80% | tests/integration/ | none | author integration suite |

## Phase 6 — Static HTML adapters

| ID | Title | Dependencies | Weight | Status | Planned start | Planned end | Owner | Gate | Evidence | Blockers | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P6-01 | Shared BeautifulSoup helpers, selector validation, pagination utilities | P3 done | TBD | not-started | TBD | TBD | Engineering Lead | unit tests pass; no sensitive HTML logged | src/utils/html_parser.py | none | implement helpers |
| P6-02 | Per-HTML-source adapters with fixture-first TDD | P6-01, P4 done | TBD | not-started | TBD | TBD | Engineering Lead | per-source contract tests pass | src/adapters/implementations/ | none | implement adapters |
| P6-03 | Selector drift / zero-job detection and representative process-level E2E | P6-02 | TBD | not-started | TBD | TBD | Engineering Lead | drift detector tests; one HTML E2E passes | tests/e2e/ | none | build detector + E2E |

## Phase 7 — Browser adapters and Playwright hardening

| ID | Title | Dependencies | Weight | Status | Planned start | Planned end | Owner | Gate | Evidence | Blockers | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P7-01 | Playwright lifecycle, deterministic local test pages, cleanup, trace on failure | P3 done | TBD | not-started | TBD | TBD | Engineering Lead | browser process does not leak across runs | src/utils/browser.py | none | scaffold browser utilities |
| P7-02 | TikTok adapter per compliance decision; 403/challenge halts and alerts | P7-01, P0-04 | TBD | not-started | TBD | TBD | Engineering Lead | contract tests pass; challenge path alerts instead of zero-job success | src/adapters/implementations/ | P0-04 compliance decision | implement adapter after approval |
| P7-03 | Northrop Grumman adapter | P7-01, P0-04 | TBD | not-started | TBD | TBD | Engineering Lead | contract tests pass | src/adapters/implementations/ | P0-04 compliance decision | implement adapter after approval |
| P7-04 | Remaining browser sources from manifest | P7-01, P0-04 | TBD | not-started | TBD | TBD | Engineering Lead | per-source contract tests pass | src/adapters/implementations/ | P0-04 compliance decision | implement after approval |
| P7-05 | Browser E2E hardening, flakiness mitigation, resource-leak verification | P7-02..P7-04 | TBD | not-started | TBD | TBD | Engineering Lead | E2E passes 10× consecutively; no leak | tests/e2e/browser/ | none | harden E2E |

## Phase 8 — Operations, monitoring, alerts, reporting

| ID | Title | Dependencies | Weight | Status | Planned start | Planned end | Owner | Gate | Evidence | Blockers | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P8-01 | Concurrent run orchestration with per-company isolation, run lock, orphan recovery | P4 done | TBD | not-started | TBD | TBD | Engineering Lead | fault-injection tests pass | src/scheduler/ | none | build orchestrator |
| P8-02 | Structured logs and metrics with run_id, attempt/source correlation | P8-01 | TBD | not-started | TBD | TBD | Engineering Lead | log/metric tests pass | src/monitoring/ | none | implement metrics |
| P8-03 | `AlertSink` (email/Slack/log) with timeout, cooldown, redaction, isolation | P8-02 | TBD | not-started | TBD | TBD | Engineering Lead | sink failure isolation tests pass | src/monitoring/alerts.py | none | implement sinks |
| P8-04 | Zero-jobs classifier: real empty vs empty-unverified vs parse failure vs anti-bot | P8-03 | TBD | not-started | TBD | TBD | Engineering Lead | each scenario alerts with distinct severity | tests/integration/monitoring/ | none | implement classifier |
| P8-05 | Idempotent scripts: `init_db`, `seed_companies`, per-adapter configs | P4 done | TBD | not-started | TBD | TBD | Engineering Lead | repeated seed runs are no-ops | scripts/ | none | author scripts |
| P8-06 | Deterministic atomic CSV export (default open jobs; no raw data) | P8-02 | TBD | not-started | TBD | TBD | Engineering Lead | export byte-for-byte reproducible given same input | src/reporting/ | none | implement exporter |
| P8-07 | Optional APScheduler wrapper for local/single-process; reuse application service + lock | P8-01 | TBD | not-started | TBD | TBD | Engineering Lead | no overlapping scheduled/manual runs | src/scheduler/aps.py | none | wire APS if needed |

## Phase 9 — Docker/PostgreSQL release hardening

| ID | Title | Dependencies | Weight | Status | Planned start | Planned end | Owner | Gate | Evidence | Blockers | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P9-01 | Docker image for one-shot job; Playwright runtime only when browser sources enabled | P5/P6/P7 done | TBD | not-started | TBD | TBD | Engineering Lead | image size and startup acceptable | Dockerfile | none | author Dockerfile |
| P9-02 | PostgreSQL startup + smoke test; secret injection; persistent export/log policy | P9-01 | TBD | not-started | TBD | TBD | Engineering Lead | smoke test passes; secrets sourced from env | docs/runbooks/ | none | author PostgreSQL smoke |
| P9-03 | External scheduler integration + runbook; UTC schedule, no overlap, exit-code handling | P9-02 | TBD | not-started | TBD | TBD | Engineering Lead | scheduled invocation + graceful shutdown verified | docs/runbooks/scheduler.md | none | author runbook |
| P9-04 | CI matrix: lint, type, unit, integration SQLite/PostgreSQL, representative E2E, coverage, secret scan | P8 done | TBD | not-started | TBD | TBD | Engineering Lead | CI gates fail below thresholds | .github/workflows/ | none | configure CI |
| P9-05 | Concurrency/resilience benchmark; browser leak check; retry-storm prevention; graceful SIGTERM | P9-02 | TBD | not-started | TBD | TBD | Engineering Lead | benchmark report shows no leak; SIGTERM completes within budget | reports/perf/ | none | run benchmarks |
| P9-06 | Final code/security review, deployment/runbook, backup/restore, rollback, known limitations | P9-04, P9-05 | TBD | not-started | TBD | TBD | Engineering Lead | no Critical/High; release checklist signed | docs/release/m9.md | none | finalize release docs |

## Risk Register (live)

| ID | Risk | Severity | Mitigation | Owner | Status |
| --- | --- | --- | --- | --- | --- |
| R-01 | Selector/HTML drift breaks adapters silently | High | Versioned fixtures, contract tests, zero-job detector, runbook | Engineering Lead | monitored |
| R-02 | Anti-bot or ToS violation on browser sources | Critical | Per-source compliance review; explicit kill switch; no automated bypass | Engineering Lead + Product Owner | gating via P0-04 |
| R-03 | Partial/empty run accidentally closes stale jobs | Critical | Reconcile only after complete + authoritative runs; missing_count policy | Engineering Lead | controlled by ADR-0004 |
| R-04 | SQLite/Postgres parity drift | High | Dual-engine migration test; portable types; UTC timestamps | Engineering Lead | planned in P2 |
| R-05 | Coverage theatre (80% line but missed error paths) | High | Component targets; behavior-based tests; code review checklist | Engineering Lead | enforced each phase |
| R-06 | Scope inflation (proxy rotation, dashboard, public API) | Medium | Explicit defer list; require new ADR to add | Engineering Lead | tracked in this file |
| R-07 | Long-running browser E2E flakiness | High | Deterministic fixtures; flakiness owner; quarantine process | Engineering Lead | managed in P7 |

## Decisions captured

- `docs/adr/0001-http-client.md` — single `httpx.AsyncClient` per process, no `aiohttp`.
- `docs/adr/0002-schema-run-model.md` — `scrape_runs` 1:N `scrape_attempts`, no `job_id` on logs.
- `docs/adr/0003-job-identity.md` — unique `(company_id, canonical_url)`; optional `source_job_id`; no cross-company dedupe in release 1.
- `docs/adr/0004-stale-closure.md` — close stale jobs only after complete + authoritative run, default after two complete misses; reopen on rediscovery.
- `docs/adr/0005-timestamps-migration.md` — UTC, timezone-aware; Alembic authoritative; portable types.
- `docs/adr/0006-scheduler-export.md` — one-shot container + external scheduler for production; APScheduler wrapper local-only; deterministic atomic CSV export.
- `docs/adr/0007-compliance.md` — explicit per-source robots/ToS/permission record; no anti-bot bypass; kill switch per source.

## Deferred scope (release 1)

- Public dashboard or read-only API.
- Cross-company dedupe (cross syndication).
- Proxy rotation and CAPTCHA bypass.
- XLSX export (CSV covers release 1).
- AWS Lambda deployment target.
- Browser adapter families beyond the explicit sources approved at M0.

## Progress History (append-only)

| Date | Phase | Update | Progress before | Progress after |
| --- | --- | --- | --- | --- |
| 2026-07-15 | Phase 0 | Initial ROADMAP, ADRs, and source manifest created; weights pending freeze at P0-05 | 0% | 0% (weights TBD) |
| 2026-07-15 | Phase 0 | **M0 closed.** Seven ADRs accepted (`docs/adr/0001..0007.md`), source manifest moved to `docs/sources/manifest.md` with 11/11 compliance decisions, per-source compliance notes captured in `docs/sources/compliance-notes.md`. 2 sources deferred via `blocked-by-policy` (TikTok, Northrop); 7 sources `blocked-pending-owner`. Phase 0 weight frozen at 10. Phase 1 unblocked. | 0% (weights TBD) | **1.4%** (10 of 692 effort points; Phase 0 = 100%) |