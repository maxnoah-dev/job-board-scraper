# Source Manifest

> Status: **Approved for M0 with 4 known sources and 7 deferred slots.**
> This manifest is the single source of truth for which sources the
> job-board scraper is allowed to touch in release 1. Sources not on this
> list are out of scope. Compliance evidence lives in
> [`compliance-notes.md`](compliance-notes.md). All compliance decisions are
> governed by [`../../adr/0007-compliance.md`](../../adr/0007-compliance.md).

## Fields

| Field | Meaning |
| --- | --- |
| `slug` | Canonical lowercase identifier used in DB and config |
| `display_name` | Human-friendly name |
| `careers_url` | Public careers landing page |
| `api_or_ats` | Backend system if known (`Greenhouse`, `Workday`, `SmartRecruiters`, `Lever`, `Teamtailor`, custom API, none) |
| `adapter_type` | `api`, `html` or `browser` |
| `expected_count_min/max` | Rough job count range from a recent sample |
| `auth_required` | `yes`/`no` — credential source must be env var |
| `rate_policy` | Minimum interval between requests, max concurrent requests |
| `authoritative_snapshot` | `true` if the source's listing page is the canonical list of all open jobs |
| `compliance_status` | `approved`, `needs-review`, `blocked`, `blocked-by-policy`, `blocked-pending-owner` |
| `fixtures_plan` | Where synthetic responses will come from |
| `owner` | Person who confirmed the source can be scraped |

## Sources

| slug | display_name | adapter_type | api_or_ats | careers_url | authoritative_snapshot | compliance_status | owner | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| opswat | OPSWAT | `api` | Greenhouse (to confirm) | https://www.opswat.com/careers | true | `needs-review` | TBD | Confirm exact board URL and auth model. Phase 4 uses synthetic fixtures only. |
| vancity | Vancity | `api` | Workday (to confirm) | https://jobs.vancity.com | true | `needs-review` | TBD | Confirm Workday tenant and public access. Phase 5 uses synthetic fixtures only. |
| tiktok | TikTok | `browser` | Custom | https://careers.tiktok.com | true | `blocked-by-policy` | TBD | Deferred for release 1 — see `compliance-notes.md`. |
| northrop | Northrop Grumman | `browser` | Custom | https://www.northropgrumman.com/careers | true | `blocked-by-policy` | TBD | Deferred for release 1 — see `compliance-notes.md`. |
| absolute-security | Absolute Security | TBD | TBD | TBD | TBD | `blocked-pending-owner` | TBD | Named in `PLAN.md`; missing URL/ATS/owner. |
| farm-credit-canada | Farm Credit Canada | TBD | TBD | TBD | TBD | `blocked-pending-owner` | TBD | Named in `PLAN.md`; missing URL/ATS/owner. |
| source-07 | (TBD) | TBD | TBD | TBD | TBD | `blocked-pending-owner` | TBD | Open slot — product owner to provide. |
| source-08 | (TBD) | TBD | TBD | TBD | TBD | `blocked-pending-owner` | TBD | Open slot — product owner to provide. |
| source-09 | (TBD) | TBD | TBD | TBD | TBD | `blocked-pending-owner` | TBD | Open slot — product owner to provide. |
| source-10 | (TBD) | TBD | TBD | TBD | TBD | `blocked-pending-owner` | TBD | Open slot — product owner to provide. |
| source-11 | (TBD) | TBD | TBD | TBD | TBD | `blocked-pending-owner` | TBD | Open slot — product owner to provide. |

## Adapter type summary

| adapter_type | sources (count) | enabled for release 1 | open questions |
| --- | --- | --- | --- |
| `api` | 2 confirmed (`opswat`, `vancity`) | yes, fixture-first | Confirm Greenhouse/Workday tenants and public access. |
| `html` | 0 confirmed | yes, scaffold only | Will be derived from `blocked-pending-owner` rows once URLs are known. |
| `browser` | 2 confirmed (`tiktok`, `northrop`) | **no** | Both deferred via `blocked-by-policy`; see `compliance-notes.md`. |

## Release 1 effective source set

After applying the compliance decisions in `compliance-notes.md`:

- 0 sources are `approved` today.
- 2 sources are `needs-review` and may proceed **only** against synthetic
  fixtures.
- 2 sources are `blocked-by-policy` and are deferred.
- 7 sources are `blocked-pending-owner` and are deferred.

The release 1 vertical slice (Phase 4) is therefore implemented entirely
against synthetic OPSWAT fixtures. Real network access is enabled only after
the product owner flips a source to `approved`.

## Per-source adapter contract (template)

For each source whose compliance status becomes `approved`, the Phase 0
deliverable must include:

1. **Entry conditions** — auth required, environment variable name, scope.
2. **Listing endpoint** — URL pattern and pagination mechanism.
3. **Field mapping** — raw field → `JobRecord` field.
4. **Canonicalization** — how `Job_URL` and date are normalized for this source.
5. **Authoritative snapshot declaration** — is missing-job signal safe?
6. **Rate policy** — per-source min interval + concurrency overrides.
7. **Failure modes** — which HTTP status codes / DOM changes trigger which
   extractor outcome (`success`, `partial`, `failed`, `empty_unverified`,
   `blocked_by_anti_bot`).
8. **Fixture plan** — which synthetic fixture will keep CI deterministic.

## Open blockers

- 7 sources (`absolute-security`, `farm-credit-canada`, `source-07..11`)
  require product owner input before they can be classified. They block
  Phase 5–7 capacity planning but do **not** block Phase 0 closure.
- `opswat` and `vancity` require product owner confirmation of their ATS
  tenant URLs before Phase 4/5 can touch the live network.
- `tiktok` and `northrop` are deferred until a compliance path is found or
  the product owner signs off on a partnership arrangement.