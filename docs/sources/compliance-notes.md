# Source Compliance Notes

> Single source of truth for whether each source in the manifest may be
> scraped, and under which constraints. Every entry below is referenced from
> `docs/sources/manifest.md` (compliance_status column) and from
> `config/adapters/<slug>.yaml` (`enabled` flag).
>
> **Policy:** No anti-bot bypass. Headless browsers may only load pages that
> the source already serves to unauthenticated visitors. CAPTCHA solving,
> residential proxy rotation, and fingerprint impersonation are out of scope.
> See `docs/adr/0007-compliance.md`.

## Status legend

| Status | Meaning |
| --- | --- |
| `approved` | Source can be scraped under the constraints listed in this file |
| `needs-review` | Decision not yet made; no implementation work allowed |
| `blocked` | Source may not be scraped in this release; kill switch forced off |
| `blocked-by-policy` | Source technically scrapeable but rejected for compliance reasons (see ADR-0007) |
| `blocked-pending-owner` | Source missing required information from product owner; cannot be classified |

## Sources

### opswat — `needs-review`

- Owner: TBD (product owner confirmation required)
- Public careers URL: https://www.opswat.com/careers (to confirm)
- ATS: Greenhouse (to confirm)
- `robots.txt` reviewed: not yet
- ToS summary: not yet captured
- Decision: leave `needs-review` until owner signs off. Adapter work for
  Phase 4 may proceed against synthetic fixtures only.

### vancity — `needs-review`

- Owner: TBD
- Public careers URL: https://jobs.vancity.com (to confirm)
- ATS: Workday (to confirm)
- `robots.txt` reviewed: not yet
- ToS summary: not yet captured
- Decision: same as opswat. Fixture-first development until owner flips
  status.

### tiktok — `blocked-by-policy`

- Owner: TBD
- Public careers URL: https://careers.tiktok.com
- ATS: custom (not publicly documented)
- `robots.txt`: careers path is disallowed for general-purpose crawlers;
  reverse-engineering of the SPA triggers anti-bot challenges.
- ToS summary: TikTok's general Terms prohibit automated access at scale to
  non-publicly documented endpoints. There is no published API for the
  careers domain.
- Decision: **deferred for release 1.** A browser adapter that respects
  this ToS would either need an explicit data-sharing agreement with TikTok
  or be limited to a tiny request rate that defeats the value of the source.
  We do not implement anti-bot bypass.
- Action: keep the entry in the manifest for audit, set
  `enabled: false` in `config/adapters/tiktok.yaml`, document the decision
  in `ROADMAP.md` deferred scope.

### northrop — `blocked-by-policy`

- Owner: TBD
- Public careers URL: https://www.northropgrumman.com/careers
- ATS: custom (Workday front-end with heavy anti-bot on the back-end)
- `robots.txt`: careers path allows general crawlers but the application
  front-end presents a Cloudflare-style challenge under load.
- ToS summary: explicit prohibition of automated access that interferes with
  normal site operation.
- Decision: **deferred for release 1.** Same reasoning as TikTok.
- Action: same as TikTok.

### absolute-security — `blocked-pending-owner`

- Owner: TBD
- Public careers URL: TBD (not provided in `PLAN.md`)
- ATS: TBD
- Decision: cannot be classified. No implementation work allowed until the
  product owner supplies the URL, ATS, and a sign-off.

### farm-credit-canada — `blocked-pending-owner`

- Owner: TBD
- Public careers URL: TBD (named in `PLAN.md` but no URL provided)
- ATS: TBD
- Decision: cannot be classified. The "zero-jobs alert" use case in
  `PLAN.md` §4 is preserved for Phase 8; we just do not yet know which
  company triggers it.

### source-07..source-11 — `blocked-pending-owner`

- Owner: TBD
- Public careers URL: TBD
- ATS: TBD
- Decision: placeholder slots. Product owner to supply name, URL, ATS and
  compliance evidence for each before Phase 1 begins.

## How to update this file

1. Update the row above.
2. Update the matching row in `docs/sources/manifest.md`.
3. Update `config/adapters/<slug>.yaml` so the `enabled` flag matches the
   new status.
4. Add a progress entry to `docs/ROADMAP.md`.
5. Do not implement code for any source whose status is not `approved`.