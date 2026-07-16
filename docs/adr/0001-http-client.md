# ADR 0001 — HTTP client

- Status: Accepted
- Date: 2026-07-15
- Phase: 0 (Scope & Decisions)
- Authors: Tech Lead
- Supersedes: none

## Context

`TECHNICAL.md` §1.1 originally proposed `asyncio + aiohttp` as the async runtime
and `aiohttp` as the default HTTP client. By the time the project moved to
implementation we already needed:

- HTTP/2 support for ATS endpoints that only expose their listing API over
  HTTP/2 (some Workday and SmartRecruiters tenants).
- First-class `Timeout`, `Limits`, and `AsyncClient` lifecycle helpers with
  predictable behaviour on `asyncio.CancelledError`.
- A single client that we can reuse for the static HTML adapters too, so that
  proxy headers, user-agent, and tracing are configured in one place.
- Type stubs that pass Pyright in strict mode without monkey patching.

`httpx` already covers all four. Mixing `aiohttp` and `httpx` adds two
connection pools and two sets of quirks (chunked encoding, proxy auth, header
canonicalisation) for no measurable benefit.

`scrapy` and `pandas` are still listed as optional in `TECHNICAL.md` §1.2, but
they pull in transitive dependencies (Twisted, lxml, numpy) that are not
required by any adapter in the release-1 manifest. They are explicitly out of
the core.

## Decision

- Use `httpx.AsyncClient` as the single HTTP client for all adapter families
  (API, HTML, and browser fallback HTTP probes).
- Do **not** introduce `aiohttp` as a dependency.
- Do **not** add `scrapy` or `pandas` to `pyproject.toml` until a concrete use
  case appears. Re-evaluate via a new ADR if and when such a use case lands.
- All adapter code goes through a single `HttpClient` wrapper
  (`src/utils/http.py`) that owns the `httpx.AsyncClient` lifecycle, timeout
  configuration, structured redacted logging, and retry classification.
- Per-source headers, cookies, and credential injection live on the adapter
  config object, not in the shared client.

## Alternatives Considered

### Alternative 1: `aiohttp` for everything

- Pros: Mature, slightly faster on plain HTTP/1.1, mature session middleware.
- Cons: No native HTTP/2, weaker Pyright story, separate stack from any
  Playwright HTTP probing code.
- Why not: HTTP/2 is required by at least one ATS tenant; the maintenance cost
  of running two HTTP stacks outweighs any single-stack performance gain.

### Alternative 2: `requests` + `asyncio.to_thread`

- Pros: Familiar API, large community.
- Cons: Blocking I/O underneath, defeats the async event loop, cannot share a
  connection pool with browser-driven requests.
- Why not: It removes the main reason we picked Python 3.11+ for this
  project.

### Alternative 3: `scrapy` as the framework

- Pros: Crawler, deduplication, and feed export built in.
- Cons: Twisted-based runtime, opinionated crawler model that does not map
  cleanly onto our adapter/ETL split, large dependency surface.
- Why not: We already have a deliberate ETL + plugin architecture. Scrapy
  would force us to re-shape the project around its crawler model.

## Consequences

- Positive: One HTTP stack, predictable timeouts, shared rate-limit headers,
  shared tracing, HTTP/2 when the server supports it.
- Positive: Pyright in strict mode passes without `type: ignore` on HTTP code
  paths.
- Negative: We must write our own retry and circuit-breaker layers (already
  scoped in Phase 3).
- Risks: If `httpx` stops being maintained, we have to migrate the whole
  stack. Mitigation: keep the dependency behind the `HttpClient` interface so
  the migration surface stays small.

## Open questions

- None at M0. We will revisit if Phase 5/6 surfaces a tenant that requires a
  feature `httpx` cannot provide.