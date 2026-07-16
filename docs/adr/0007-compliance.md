# ADR 0007 — Source compliance policy

- Status: Accepted
- Date: 2026-07-15
- Phase: 0 (Scope & Decisions)
- Authors: Tech Lead + Product Owner
- Supersedes: none

## Context

`PLAN.md` §4 names "anti-bot bypass" as a real technical risk for TikTok and
Northrop Grumman. `TECHNICAL.md` §8 lists "switch to browser mode" as a
recovery strategy for anti-bot challenges, which is the wrong default for a
compliance-first project.

A data scraper must respect the rules of each target. Anything else exposes
the project to legal and reputational risk that outweighs the value of one
extra source.

## Decision

- Every source listed in `docs/sources/manifest.md` must have a written
  compliance record (`docs/sources/compliance-notes.md`) covering:
  1. `robots.txt` allowance for the careers path.
  2. Terms of Service summary relevant to automated access.
  3. Whether the source publishes an API or ATS and whether its terms
     explicitly forbid scraping of the public HTML page.
  4. Decision: `approved`, `needs-review`, `blocked`.
- **No source may implement an anti-bot bypass.** Headless browsers are
  permitted only to load public pages that the source already serves to
  unauthenticated visitors; they may not impersonate specific device
  fingerprints, rotate residential proxies, or solve CAPTCHAs.
- A source whose compliance status is `needs-review` cannot start Phase 7
  (browser) work until a human product owner flips it to `approved` or
  `blocked`.
- A source marked `blocked` may not appear in any Phase-5+ deliverable.
  Adapters for blocked sources are removed from the registry at startup.
- Each adapter exposes a per-source **kill switch** in
  `config/adapters/<slug>.yaml` (`enabled: false`). Setting the switch is a
  runtime decision; it does not require a code change.
- The `compliance_status` column on the manifest is the single source of
  truth. Phase 0 must close with all 11 sources marked.

## Alternatives Considered

### Alternative 1: Implement anti-bot bypass for TikTok and Northrop

- Pros: More sources in release 1.
- Cons: Legal exposure, reputational risk, IP-ban risk, and ethical concerns
  about violating target servers' explicit access policies.
- Why not: Out of scope. Deferred.

### Alternative 2: Silent scraping without a compliance record

- Pros: Faster to ship.
- Cons: Impossibly hard to audit, impossible to defend in a review.
- Why not: A documented record is a release-1 requirement.

### Alternative 3: One global kill switch

- Pros: Trivial implementation.
- Cons: Cannot disable a single bad source without disabling the whole
  pipeline.
- Why not: Per-source granularity is required by the alerting story in
  Phase 8.

## Consequences

- Positive: Auditable, defensible, and reversible. Each source can be
  disabled in seconds.
- Negative: Some sources (TikTok, Northrop, and others with strong anti-bot)
  are deferred. They can come back in a later release once a compliance path
  is found.
- Risks: A future engineer might be tempted to add a bypass "just for
  testing." Mitigation: the kill switch is enforced by tests in Phase 7, and
  the registry refuses to load bypass-flagged adapters.

## Open questions

- None at M0. The deferred list lives in `ROADMAP.md` "Deferred scope".