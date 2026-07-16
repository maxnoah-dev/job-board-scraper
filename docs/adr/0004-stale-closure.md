# ADR 0004 — Stale job closure policy

- Status: Accepted
- Date: 2026-07-15
- Phase: 0 (Scope & Decisions)
- Authors: Tech Lead
- Supersedes: none
- Related: ADR-0002 (schema), ADR-0003 (job identity)

## Context

`PLAN.md` §3 step 4 says we must close jobs that "no longer appear in the
latest scrape." That sentence is dangerously literal. A partial run (one
adapter failed) or an empty result from a misconfigured adapter must not
close the jobs of an entire company. Likewise, a transient anti-bot
challenge that returns zero jobs is not a signal that every job has been
filled.

We need an explicit rule that ties closure to *confidence* in the run, not
just to absence.

## Decision

A job is eligible for `closed` status only when **all** of the following are
true for the most recent run that observed its company:

1. `scrape_attempts.complete = true` (every expected page/response was
   processed, not just one page that came back empty).
2. `scrape_attempts.authoritative_snapshot = true` for that company
   (declared per source; see `docs/sources/manifest.md`).
3. The job's `(company_id, canonical_url)` was **not** seen in the current
   run, and the company's run-level `missing_count` for that job is ≥ 2
   (default `MAX_MISSES_BEFORE_CLOSE = 2`).
4. The job's `last_seen_at` is older than the run's `started_at`.

The reconcile step is the **only** place that flips `open → closed`. Adapters
never mutate `jobs.status`.

A job that reappears after being closed is reopened
(`closed → open`), and `last_seen_at` is reset. Closure is not destructive;
historical rows are preserved for audit.

A run with `status` of `partial`, `failed`, `cancelled`, `interrupted`, or
with `authoritative_snapshot = false` does **not** contribute to the
`missing_count` counter.

## Alternatives Considered

### Alternative 1: Close after one miss

- Pros: Fastest reconciliation.
- Cons: Any single transient failure closes every open job for that
  company. Catastrophic for data quality.
- Why not: Fails the "no silent failure" gate in Phase 8.

### Alternative 2: Close after a fixed time window (e.g., 7 days unseen)

- Pros: Time-based, easy to explain.
- Cons: Independent of the actual scraping schedule, lets stale jobs linger
  past the next successful run, requires a separate cron.
- Why not: We already have a run signal; using it is more accurate.

### Alternative 3: Manual closure only

- Pros: Zero false closures.
- Cons: Operator overhead, defeats the purpose of automation, and `PLAN.md`
  explicitly asks for automatic closure.
- Why not: Out of scope of the release goal.

## Consequences

- Positive: Safe by default. Partial and failed runs cannot accidentally
  close jobs. Reopen on rediscovery is supported.
- Negative: Jobs may stay "open" for one extra run cycle after they
  disappear. This is the price of safety and is documented in the runbook.
- Risks: A source that never produces an `authoritative_snapshot = true`
  result will never close jobs. Mitigation: per-source authoritative flag is
  reviewed in Phase 0 and revisited in Phase 8.

## Open questions

- None at M0. Threshold parameter is configurable via env
  (`MAX_MISSES_BEFORE_CLOSE`).