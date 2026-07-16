# ADR 0005 — Timestamps & database migration

- Status: Accepted
- Date: 2026-07-15
- Phase: 0 (Scope & Decisions)
- Authors: Tech Lead
- Supersedes: none

## Context

`PLAN.md` and `TECHNICAL.md` do not currently specify a timezone policy. The
project must run in Vietnam (UTC+7) and in CI/cloud environments that default
to UTC. A naive timestamp that assumes "local time" causes off-by-N-hours
bugs that are extremely painful to debug.

In addition, the project must run on SQLite locally and on PostgreSQL in
production. `TECHNICAL.md` lists `SQLAlchemy` + `aiosqlite` but does not lock
down how schema changes are applied.

## Decision

### Timestamps

- All timestamps in code, logs, and the database are stored in UTC.
- All SQLAlchemy columns use `DateTime(timezone=True)` mapped onto
  `TIMESTAMP WITH TIME ZONE` on PostgreSQL and ISO-8601 strings on SQLite.
- Pydantic models expose `datetime` fields that are timezone-aware; the
  validator rejects naive datetimes with a clear error.
- The CLI prints timestamps in UTC by default and accepts an optional
  `--tz` flag for display only.

### Migrations

- Use **Alembic** as the authoritative migration tool. SQLAlchemy `metadata.create_all`
  is **not** an acceptable substitute for environments where `init_db` runs
  against existing data.
- Migrations are tested on both SQLite and PostgreSQL during Phase 2 (CI
  matrix) and again in Phase 9 (release hardening).
- Each migration file must contain both `upgrade()` and `downgrade()` and must
  be reversible without data loss for the columns we care about (URL,
  status, timestamps).

### Database engine

- Local dev and tests: `sqlite+aiosqlite:///./data/jobs.db`.
- Production: `postgresql+asyncpg://...`, with the DSN injected via
  environment variable `DATABASE_URL`.
- SQLAlchemy 2.x async API only.

## Alternatives Considered

### Alternative 1: Store local time (Asia/Ho_Chi_Minh)

- Pros: Operator comfort in Vietnam.
- Cons: DST / daylight savings drift in other environments, ambiguous audit
  trail, harder CI reproducibility.
- Why not: UTC is the only safe default for a multi-timezone project.

### Alternative 2: `metadata.create_all()` only, no Alembic

- Pros: Zero migration tooling.
- Cons: Cannot evolve the schema in production without data loss, cannot
  downgrade, no audit trail.
- Why not: Phase 2 explicitly requires Alembic.

### Alternative 3: Plain SQL files, no ORM migration tool

- Pros: Full control.
- Cons: Easy to drift from SQLAlchemy models, harder to test, no
  autogenerate for minor changes.
- Why not: Alembic already integrates with our chosen ORM.

## Consequences

- Positive: Reproducible runs across timezones; schema is reversible; CI
  catches drift early.
- Negative: One more dependency (Alembic) and a migration test matrix.
- Risks: PostgreSQL/SQLite type parity. Mitigation: the Phase 2 dual-engine
  test gates every migration.

## Open questions

- None at M0. CI matrix shape is finalised in Phase 9.