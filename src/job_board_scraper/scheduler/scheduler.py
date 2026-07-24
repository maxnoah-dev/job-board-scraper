"""Concurrent run orchestration and scheduling.

Manages concurrent scrape runs with per-company isolation, run locking,
orphan recovery, and APScheduler integration.
"""

from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from job_board_scraper.adapters.base import BaseAdapter


class RunState(Enum):
    """State of a scrape run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class RunLock:
    """A lock for a running scrape operation."""

    run_id: str
    started_at: datetime
    companies: list[str]
    pid: int | None = None


class RunLockManager:
    """Manages run locks to prevent overlapping runs."""

    def __init__(self) -> None:
        self._locks: dict[str, RunLock] = {}

    @asynccontextmanager
    async def acquire(self, run_id: str, companies: list[str]) -> RunLock:
        """Acquire a lock for a run.

        Raises RuntimeError if another run is already in progress.
        """
        if self.is_locked:
            raise RuntimeError(
                f"Cannot start run {run_id}: another run is already in progress "
                f"(run_id={self.active_run_id})"
            )

        lock = RunLock(
            run_id=run_id,
            started_at=datetime.now(UTC),
            companies=companies,
            pid=None,
        )
        self._locks[run_id] = lock
        try:
            yield lock
        finally:
            self._locks.pop(run_id, None)

    @property
    def is_locked(self) -> bool:
        """Check if any run is currently in progress."""
        return len(self._locks) > 0

    @property
    def active_run_id(self) -> str | None:
        """Get the active run ID if any."""
        return next(iter(self._locks.keys())) if self._locks else None

    def get_lock(self, run_id: str) -> RunLock | None:
        """Get a specific lock by run ID."""
        return self._locks.get(run_id)


class ConcurrentOrchestrator:
    """Orchestrates concurrent scrape runs with semaphore limiting."""

    def __init__(
        self,
        max_concurrent: int = 5,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._lock_manager = RunLockManager()

    @property
    def max_concurrent(self) -> int:
        """Get the maximum concurrent adapter limit."""
        return self._semaphore._value  # type: ignore

    async def run_adapter(
        self,
        adapter: BaseAdapter,
        run_id: str,
    ) -> tuple[bool, int, list[str]]:
        """Run a single adapter with semaphore, retries, and rate limiting.

        Returns:
            Tuple of (success, jobs_found, errors)
        """
        errors: list[str] = []
        jobs_found = 0

        for attempt in range(self._max_retries + 1):
            try:
                async with self._semaphore:
                    result = await adapter.fetch_jobs()
                    jobs_found = len(result.jobs)

                    if result.status.value == "success":
                        return True, jobs_found, []
                    elif result.status.value == "partial":
                        errors.extend(result.warnings)
                        return True, jobs_found, result.warnings
                    else:
                        errors.append(result.error or "Unknown error")
                        if attempt < self._max_retries:
                            await asyncio.sleep(self._retry_delay * (attempt + 1))
                            continue
                        return False, jobs_found, errors

            except Exception as e:
                errors.append(str(e))
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay * (attempt + 1))
                    continue
                return False, jobs_found, errors

        return False, jobs_found, errors

    def generate_run_id(self) -> str:
        """Generate a unique run ID."""
        return f"run_{uuid.uuid4().hex[:12]}"

    @property
    def lock_manager(self) -> RunLockManager:
        """Get the run lock manager."""
        return self._lock_manager


class OrphanRecovery:
    """Recovers from orphan processes left by interrupted runs."""

    def __init__(self) -> None:
        self._recovered_runs: list[str] = []

    def mark_recovered(self, run_id: str) -> None:
        """Mark a run as recovered from orphan state."""
        self._recovered_runs.append(run_id)

    def get_recovered(self) -> list[str]:
        """Get list of recovered run IDs."""
        return self._recovered_runs.copy()


# Global orchestrator instance
_orchestrator: ConcurrentOrchestrator | None = None


def get_orchestrator() -> ConcurrentOrchestrator:
    """Get or create the global orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ConcurrentOrchestrator()
    return _orchestrator


# Global lock manager instance
_lock_manager: RunLockManager | None = None


def get_lock_manager() -> RunLockManager:
    """Get or create the global lock manager."""
    global _lock_manager
    if _lock_manager is None:
        _lock_manager = RunLockManager()
    return _lock_manager
