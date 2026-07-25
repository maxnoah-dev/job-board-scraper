"""Scrape trigger service.

Manages a single in-flight scrape run per process. Two responsibilities:

1. **Mutual exclusion**: while a run is in flight, a second ``start()``
   call must be refused with ``ScrapeTriggerError``. This protects target
   servers from accidental stampedes when two UI tabs click "Run" at
   once.
2. **Background execution**: ``start()`` returns the ``run_id`` as soon
   as the pipeline has created its DB row; the actual scraping then
   continues asynchronously so the HTTP request returns immediately.

The class deliberately keeps state in-process (asyncio.Event + a dict)
because the dashboard runs as a single uvicorn worker in the supported
deployment topologies. If a multi-worker setup is ever introduced, the
lock would need to move to Postgres advisory locks — out of scope here.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from job_board_scraper.etl.pipeline import (
    PipelineExitCode,
    ScrapingPipeline,
    create_pipeline,
)
from job_board_scraper.models import RunStatus, ScrapeRun
from job_board_scraper.core.database import session_scope

logger = logging.getLogger(__name__)


class ScrapeTriggerError(RuntimeError):
    """Raised when a trigger operation cannot proceed.

    Carries an HTTP-friendly status code so the API layer can map it
    directly to a response without leaking internal state.
    """

    def __init__(self, message: str, *, status_code: int = 409) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class RunSnapshot:
    """Snapshot of the trigger's current state, returned by ``status()``."""

    state: str  # "idle" | "running"
    run_id: int | None = None
    triggered_by: str | None = None
    company_slug: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    last_status: str | None = None
    last_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "run_id": self.run_id,
            "triggered_by": self.triggered_by,
            "company_slug": self.company_slug,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "last_status": self.last_status,
            "last_error": self.last_error,
        }


@dataclass
class _RunContext:
    """Internal mutable state for an in-flight or recently-finished run."""

    run_id: int
    triggered_by: str
    company_slug: str | None
    started_at: datetime
    finished_at: datetime | None = None
    last_status: str | None = None
    last_error: str | None = None
    # Set when the pipeline task finishes; consumers (status polling)
    # await it instead of polling the DB to avoid noisy queries.
    done: asyncio.Event = field(default_factory=asyncio.Event)


class ScrapeTrigger:
    """Coordinates manual scrape runs triggered from the web UI."""

    def __init__(self, pipeline_factory: Any | None = None) -> None:
        # ``pipeline_factory`` is held by reference, but the default
        # factory is looked up via the module namespace on each
        # invocation (see ``_resolve_factory``). This means tests that
        # monkeypatch
        # ``job_board_scraper.web.services.scrape_trigger.create_pipeline``
        # are honored even when the trigger was constructed before the
        # patch took effect.
        self._pipeline_factory = pipeline_factory
        self._lock = asyncio.Lock()
        self._current: _RunContext | None = None
        self._last: RunSnapshot | None = None
        self._task: asyncio.Task[None] | None = None

    def _resolve_factory(self) -> Any:
        if self._pipeline_factory is not None:
            return self._pipeline_factory
        # Resolve through the *module* attribute rather than the local
        # ``create_pipeline`` import, so monkeypatching the module works.
        import job_board_scraper.web.services.scrape_trigger as mod

        return mod.create_pipeline

    async def start(
        self,
        *,
        company_slug: str | None = None,
        triggered_by: str = "ui",
        dry_run: bool = False,
    ) -> RunSnapshot:
        """Start a new scrape run.

        Returns a ``RunSnapshot`` whose ``state == "running"`` and whose
        ``run_id`` has been persisted in the database. The actual scrape
        proceeds in a background task created by this method.

        Raises:
            ScrapeTriggerError: if a run is already in progress.
        """
        async with self._lock:
            if self._current is not None and not self._current.done.is_set():
                raise ScrapeTriggerError(
                    "A scrape is already running; please wait until it finishes."
                )

            pipeline_factory = self._resolve_factory()
            pipeline: ScrapingPipeline = pipeline_factory()

            # Create the DB row up front so we can return its ID to the
            # client immediately. Mirrors the behavior of
            # ``ScrapingPipeline._create_run`` but keeps the trigger
            # service decoupled from the pipeline's private methods.
            run_id = await self._create_run_row(triggered_by)

            ctx = _RunContext(
                run_id=run_id,
                triggered_by=triggered_by,
                company_slug=company_slug,
                started_at=datetime.now(UTC),
            )
            self._current = ctx
            self._task = asyncio.create_task(
                self._run_pipeline(pipeline, ctx, company_slug, dry_run),
                name=f"scrape-run-{run_id}",
            )

            logger.info(
                "Scrape run started",
                extra={"run_id": run_id, "triggered_by": triggered_by},
            )
            return self._snapshot_from_context(ctx)

    async def status(self) -> RunSnapshot:
        """Return the current state of the trigger."""
        async with self._lock:
            if self._current is None:
                if self._last is not None:
                    return self._last
                return RunSnapshot(state="idle")
            return self._snapshot_from_context(self._current)

    async def _run_pipeline(
        self,
        pipeline: ScrapingPipeline,
        ctx: _RunContext,
        company_slug: str | None,
        dry_run: bool,
    ) -> None:
        """Execute the pipeline and update the trigger's bookkeeping."""
        try:
            slugs = [company_slug] if company_slug else None
            result = await pipeline.run(
                company_slugs=slugs,
                dry_run=dry_run,
                triggered_by=ctx.triggered_by,
            )
            ctx.last_status = self._pipeline_status_name(result.status)
            ctx.finished_at = datetime.now(UTC)
            self._last = self._snapshot_from_context(ctx)
            logger.info(
                "Scrape run finished",
                extra={
                    "run_id": ctx.run_id,
                    "status": ctx.last_status,
                },
            )
        except Exception as exc:  # noqa: BLE001 — top-level guard
            logger.exception(
                "Scrape run crashed",
                extra={"run_id": ctx.run_id},
            )
            ctx.last_status = RunStatus.FAILED.value
            ctx.last_error = str(exc)
            ctx.finished_at = datetime.now(UTC)
            self._last = self._snapshot_from_context(ctx)
        finally:
            async with self._lock:
                ctx.done.set()
                # Leave ``self._current`` populated until the next start()
                # call so ``status()`` can still report the last run.

    async def _create_run_row(self, triggered_by: str) -> int:
        """Insert a fresh ScrapeRun row and return its primary key."""
        async with session_scope() as session:
            run = ScrapeRun(
                started_at=datetime.now(UTC),
                status=RunStatus.RUNNING.value,
                triggered_by=triggered_by,
            )
            session.add(run)
            await session.flush()
            return int(run.id)

    @staticmethod
    def _snapshot_from_context(ctx: _RunContext) -> RunSnapshot:
        return RunSnapshot(
            state="running" if not ctx.done.is_set() else "finished",
            run_id=ctx.run_id,
            triggered_by=ctx.triggered_by,
            company_slug=ctx.company_slug,
            started_at=ctx.started_at,
            finished_at=ctx.finished_at,
            last_status=ctx.last_status,
            last_error=ctx.last_error,
        )

    @staticmethod
    def _pipeline_status_name(exit_code: PipelineExitCode) -> str:
        mapping = {
            PipelineExitCode.SUCCESS: RunStatus.SUCCESS.value,
            PipelineExitCode.PARTIAL: RunStatus.PARTIAL.value,
            PipelineExitCode.FAILED: RunStatus.FAILED.value,
        }
        return mapping.get(exit_code, RunStatus.FAILED.value)


# Module-level singleton — reset by tests via ``_trigger = None``.
_trigger: ScrapeTrigger | None = None


def get_trigger() -> ScrapeTrigger:
    """Return the process-wide ScrapeTrigger instance."""
    global _trigger
    if _trigger is None:
        _trigger = ScrapeTrigger()
    return _trigger
