"""Tests for the package skeleton that gate Phase 1 (P1-02).

These tests verify that the ``src/job_board_scraper/`` tree matches the
contract defined in ``docs/TECHNICAL.md`` §4 (Directory Structure) and that
no circular import exists between any two packages.

Gate evidence required by `docs/ROADMAP.md` Phase 1 row P1-02:
- package import smoke — all declared packages are importable
- no circular imports between any two modules in the tree
- ``src/job_board_scraper/__init__.py`` exposes ``__version__``
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = PROJECT_ROOT / "src" / "job_board_scraper"

# The complete module namespace declared in TECHNICAL.md §4 + CLI entry point.
EXPECTED_PACKAGES: list[str] = [
    # CLI
    "job_board_scraper.cli",
    # core/
    "job_board_scraper.core",
    "job_board_scraper.core.base",
    "job_board_scraper.core.config",
    "job_board_scraper.core.database",
    "job_board_scraper.core.logging",
    # models/
    "job_board_scraper.models",
    "job_board_scraper.models.job",
    "job_board_scraper.models.company",
    "job_board_scraper.models.db_company",
    "job_board_scraper.models.db_job",
    "job_board_scraper.models.db_scrape_attempt",
    "job_board_scraper.models.db_scrape_run",
    "job_board_scraper.models.scrape_log",
    # repositories/
    "job_board_scraper.repositories",
    "job_board_scraper.repositories.job_repository",
    "job_board_scraper.repositories.company_repository",
    "job_board_scraper.repositories.scrape_log_repository",
    # etl/
    "job_board_scraper.etl",
    "job_board_scraper.etl.base",
    "job_board_scraper.etl.extractor",
    "job_board_scraper.etl.transformer",
    "job_board_scraper.etl.loader",
    "job_board_scraper.etl.deduplicator",
    "job_board_scraper.etl.pipeline",
    "job_board_scraper.etl.stale_reconciler",
    "job_board_scraper.etl.multi_adapter",
    # adapters/
    "job_board_scraper.adapters",
    "job_board_scraper.adapters.base",
    "job_board_scraper.adapters.config",
    "job_board_scraper.adapters.registry",
    "job_board_scraper.adapters.protocols",
    "job_board_scraper.adapters.protocols.api_adapter",
    "job_board_scraper.adapters.protocols.html_adapter",
    "job_board_scraper.adapters.protocols.browser_adapter",
    "job_board_scraper.adapters.implementations",
    "job_board_scraper.adapters.implementations.opswat_adapter",
    "job_board_scraper.adapters.implementations.vancity_adapter",
    "job_board_scraper.adapters.implementations.techcorp_adapter",
    "job_board_scraper.adapters.implementations.tiktok_adapter",
    "job_board_scraper.adapters.implementations.northrop_adapter",
    "job_board_scraper.adapters.implementations.startup_xyz_adapter",
    # monitoring/
    "job_board_scraper.monitoring",
    "job_board_scraper.monitoring.alert_manager",
    "job_board_scraper.monitoring.metrics",
    "job_board_scraper.monitoring.detectors",
    "job_board_scraper.monitoring.selector_drift",
    # scheduler/
    "job_board_scraper.scheduler",
    "job_board_scraper.scheduler.scheduler",
    "job_board_scraper.scheduler.jobs",
    # utils/
    "job_board_scraper.utils",
    "job_board_scraper.utils.rate_limiter",
    "job_board_scraper.utils.retry",
    "job_board_scraper.utils.user_agents",
    "job_board_scraper.utils.circuit_breaker",
    "job_board_scraper.utils.http",
    "job_board_scraper.utils.html_parser",
    "job_board_scraper.utils.browser",
    # reporting/
    "job_board_scraper.reporting",
    "job_board_scraper.reporting.csv_exporter",
    # web/
    "job_board_scraper.web",
    "job_board_scraper.web.app",
    "job_board_scraper.web.routes",
    "job_board_scraper.web.routes.api",
    "job_board_scraper.web.routes.companies",
    "job_board_scraper.web.routes.dashboard",
    "job_board_scraper.web.routes.jobs",
    "job_board_scraper.web.routes.runs",
]

# Directed edges that represent allowed imports between modules.
# Any import chain that creates a cycle back to the importer is a failure.
# Note: intra-package imports (same package) are not checked since
# importing B in package A will always load A.__init__ first.
_ALLOWED_IMPORTS: set[tuple[str, str]] = {
    # ETL
    ("job_board_scraper.etl.extractor", "job_board_scraper.models.job"),
    ("job_board_scraper.etl.extractor", "job_board_scraper.adapters.registry"),
    ("job_board_scraper.etl.transformer", "job_board_scraper.models.job"),
    ("job_board_scraper.etl.base", "job_board_scraper.etl.extractor"),
    ("job_board_scraper.etl.base", "job_board_scraper.etl.transformer"),
    ("job_board_scraper.etl.base", "job_board_scraper.etl.loader"),
    ("job_board_scraper.etl.base", "job_board_scraper.etl.deduplicator"),
    ("job_board_scraper.etl.pipeline", "job_board_scraper.adapters.base"),
    ("job_board_scraper.etl.stale_reconciler", "job_board_scraper.models.job"),
    # Repositories
    ("job_board_scraper.repositories.job_repository", "job_board_scraper.models.job"),
    (
        "job_board_scraper.repositories.job_repository",
        "job_board_scraper.models.db_job",
    ),
    (
        "job_board_scraper.repositories.company_repository",
        "job_board_scraper.models.db_company",
    ),
    (
        "job_board_scraper.repositories.scrape_log_repository",
        "job_board_scraper.models.db_scrape_run",
    ),
    (
        "job_board_scraper.repositories.scrape_log_repository",
        "job_board_scraper.models.db_scrape_attempt",
    ),
    (
        "job_board_scraper.repositories.scrape_log_repository",
        "job_board_scraper.models.db_company",
    ),
    # Scheduler
    ("job_board_scraper.scheduler.scheduler", "job_board_scraper.core.logging"),
    # Monitoring
    ("job_board_scraper.monitoring.alert_manager", "job_board_scraper.core.logging"),
    # CLI
    ("job_board_scraper.cli", "job_board_scraper.etl"),
    # Web
    ("job_board_scraper.web.app", "job_board_scraper.core.database"),
    (
        "job_board_scraper.web.routes.dashboard",
        "job_board_scraper.repositories.company_repository",
    ),
    (
        "job_board_scraper.web.routes.dashboard",
        "job_board_scraper.repositories.scrape_log_repository",
    ),
    (
        "job_board_scraper.web.routes.runs",
        "job_board_scraper.repositories.scrape_log_repository",
    ),
    (
        "job_board_scraper.web.routes.companies",
        "job_board_scraper.repositories.company_repository",
    ),
    (
        "job_board_scraper.web.routes.jobs",
        "job_board_scraper.repositories.job_repository",
    ),
}


def _resolve_module_names() -> set[str]:
    """Walk the package tree and return all importable module names.

    Both styles are handled:
    - adapters/base.py         → job_board_scraper.adapters.base
    - adapters/protocols/__init__.py → job_board_scraper.adapters.protocols
    """
    if not PACKAGE_ROOT.exists():
        return set()

    pkg_root_resolved = PACKAGE_ROOT.resolve()
    actual: set[str] = set()

    # Packages (directories with __init__.py)
    for init_path in pkg_root_resolved.rglob("__init__.py"):
        rel = init_path.parent.relative_to(pkg_root_resolved)
        parts = rel.parts
        if parts:
            actual.add("job_board_scraper." + ".".join(parts))
        else:
            actual.add("job_board_scraper")

    # Flat modules (file.py inside a package)
    for py_path in pkg_root_resolved.rglob("*.py"):
        if py_path.name == "__init__.py":
            continue
        rel = py_path.relative_to(pkg_root_resolved)
        parts = rel.parts
        # e.g. ("adapters", "base.py") → ("adapters",) for parent
        parent_dotted = ".".join(parts[:-1])
        stem = parts[-1][:-3]  # strip .py
        if parent_dotted:
            actual.add(f"job_board_scraper.{parent_dotted}.{stem}")
        else:
            actual.add(f"job_board_scraper.{stem}")

    actual.discard("job_board_scraper")  # root package not in EXPECTED_PACKAGES
    return actual


class TestPackageTree:
    """All declared packages from TECHNICAL.md §4 must exist and be importable."""

    @pytest.mark.parametrize("module_name", EXPECTED_PACKAGES)
    def test_module_exists_and_is_importable(self, module_name: str) -> None:
        """Every module listed in TECHNICAL.md §4 must be importable."""
        try:
            importlib.import_module(module_name)
        except ImportError as exc:
            pytest.fail(
                f"Cannot import {module_name!r} — missing module or "
                f"missing `__init__.py` in its package: {exc}"
            )

    def test_all_expected_packages_present(self) -> None:
        """Actual package tree must be a superset of the declared set."""
        actual = _resolve_module_names()
        missing = set(EXPECTED_PACKAGES) - actual
        extra = actual - set(EXPECTED_PACKAGES)
        if missing:
            pytest.fail(
                f"Expected packages not found under {PACKAGE_ROOT}: "
                f"{sorted(missing)}. Add the missing module files."
            )
        if extra:
            pytest.fail(
                f"Unexpected extra packages found under {PACKAGE_ROOT}: "
                f"{sorted(extra)}. Either remove them or update TECHNICAL.md §4."
            )


class TestCircularImports:
    """Detect accidental circular import chains between packages."""

    @pytest.mark.slow
    @pytest.mark.parametrize(
        "importer",
        sorted({e[0] for e in _ALLOWED_IMPORTS}),
    )
    def test_no_circular_imports(self, importer: str) -> None:
        """Allowed import chains must not create a cycle back to the importer."""
        allowed_deps = {e[1] for e in _ALLOWED_IMPORTS if e[0] == importer}

        for dep in sorted(allowed_deps):
            # Fresh sys.modules state for each pair
            to_clear = [k for k in sys.modules if k.startswith("job_board_scraper.")]
            for key in to_clear:
                del sys.modules[key]

            try:
                importlib.import_module(dep)
            except ImportError:
                pytest.skip(f"{dep!r} not importable yet; P1-02 GREEN incomplete")
                return

            if importer in sys.modules:
                for key in list(sys.modules.keys()):
                    if key.startswith("job_board_scraper."):
                        del sys.modules[key]
                pytest.fail(
                    f"Circular import: importing {dep!r} pulled in {importer!r}. "
                    "Review the import chain."
                )


class TestPackageVersion:
    """``__version__`` must be exposed from the package root."""

    def test_version_exposed_on_package_root(self) -> None:
        """The root package must expose ``__version__``."""
        import job_board_scraper

        assert hasattr(job_board_scraper, "__version__")
        assert isinstance(job_board_scraper.__version__, str)
