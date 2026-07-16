# ADR 0003 — Job identity & deduplication

- Status: Accepted
- Date: 2026-07-15
- Phase: 0 (Scope & Decisions)
- Authors: Tech Lead
- Supersedes: none
- Related: ADR-0002 (schema), ADR-0004 (stale closure)

## Context

Jobs are scraped from heterogeneous sources. We need a deterministic way to
decide whether a scraped record refers to the same job we have already stored.
The wrong identity rule causes both silent duplicates and over-eager closure
of legitimate jobs.

`PLAN.md` §2 names `Job_URL` as the dedupe key. We must decide what shape of
URL counts as canonical, whether the source-provided identifier (`source_job_id`)
should also be unique, and whether dedupe spans companies.

## Decision

- Store both the raw source URL and a `canonical_url` on every job row.
  `canonical_url` is the result of a source-specific canonicalizer
  (UTM/tracking query strip, fragment strip, hostname lower-case, trailing
  slash normalisation, default-port strip).
- Unique constraint on `(company_id, canonical_url)`.
- Optional `source_job_id` with `UNIQUE (company_id, source_job_id)` enforced
  only when the source provides a stable identifier. Sources that reuse IDs
  (e.g., Greenhouse req IDs are stable; some Workday tenant IDs are not) do
  not get this constraint.
- **No cross-company dedupe in release 1.** A job that the same person sees on
  two companies is recorded twice. This is explicitly deferred (see
  `ROADMAP.md` "Deferred scope").
- The transformer is the only place that produces a `canonical_url`. Adapters
  emit raw URLs only.

## Alternatives Considered

### Alternative 1: `Job_URL` only, no canonicalisation

- Pros: Simplest rule, fastest to implement.
- Cons: Two identical postings with different UTM parameters become two rows;
  re-shared links produce false "new job" alerts.
- Why not: Real-world job boards all use UTM params in social shares.

### Alternative 2: Hash of `(title, company_id, location)` as identity

- Pros: Survives URL reshuffles.
- Cons: Collisions on similar titles, churn on minor wording changes, very
  expensive to debug.
- Why not: URL is the contract with the applicant; we should preserve it.

### Alternative 3: Cross-company dedupe via fuzzy matching

- Pros: Looks nice on a dashboard.
- Cons: Needs manual review workflow, false positives are operationally
  expensive, and it is out of scope for release 1.
- Why not: Deferred. See `ROADMAP.md` deferred scope.

## Consequences

- Positive: Deterministic identity, low false-positive rate, easy to debug.
- Negative: One more table column, one more canonicalizer per source.
- Risks: Bad canonicalizer on a single source can create duplicate rows.
  Mitigation: each canonicalizer is unit-tested in Phase 2 with positive and
  negative fixtures, and integration-tested in Phase 4 with OPSWAT.

## Open questions

- None at M0. The canonicalizer list lives next to the source adapter config
  (see `docs/sources/manifest.md`).