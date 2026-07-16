"""Tests for Poetry project metadata that gate Phase 1.

These tests inspect the on-disk project files (`pyproject.toml`, source
layout) so the build system fails fast when the project skeleton drifts
out of the contract agreed at M1.

Gate evidence required by `docs/ROADMAP.md` Phase 1 row P1-01:
- clean install + import smoke pass
- `pyproject.toml` and `poetry.lock` exist
- Python >= 3.11 pin
- dependency groups (runtime, dev) declared
- console scripts wired to actual entry points
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = PROJECT_ROOT / "pyproject.toml"


def _load_pyproject() -> dict:
    assert PYPROJECT.exists(), "pyproject.toml must exist at repo root (P1-01 gate)"
    with PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)


class TestPoetryProjectMetadata:
    """Static checks on `pyproject.toml` enforced by P1-01."""

    def test_pyproject_declares_project_name(self) -> None:
        meta = _load_pyproject()
        project = meta.get("project", {})
        assert (
            project.get("name") == "job-board-scraper"
        ), f"project.name must be 'job-board-scraper', got {project.get('name')!r}"

    def test_pyproject_pin_python_311_or_newer(self) -> None:
        meta = _load_pyproject()
        requires = meta.get("project", {}).get("requires-python", "")
        # Poetry convention: ">=3.11" or ">=3.11,<4.0"
        assert requires.startswith(">=3.11") or requires.startswith(
            ">=3.12"
        ), f"requires-python must allow Python 3.11+, got {requires!r}"

    def test_pyproject_declares_dependency_groups(self) -> None:
        meta = _load_pyproject()
        dep_groups = meta.get("dependency-groups", {})
        deps = meta.get("project", {}).get("dependencies", [])
        # Either PEP 621 dependencies or PEP 735 dependency-groups must be populated
        assert (
            len(deps) > 0 or len(dep_groups) > 0
        ), "pyproject.toml must declare runtime dependencies or PEP 735 groups"

    def test_pyproject_includes_dev_dependency_group(self) -> None:
        meta = _load_pyproject()
        # PEP 735 uses the key [dependency-groups]. Older Poetry layouts use
        # [tool.poetry.group.<name>.dependencies]. Both are acceptable.
        dep_groups = meta.get("dependency-groups", {})
        poetry_groups = (
            meta.get("tool", {}).get("poetry", {}).get("group", {})
        )
        assert (
            "dev" in dep_groups
            or "test" in dep_groups
            or "dev" in poetry_groups
        ), (
            "pyproject.toml must declare a dev/test dependency group for"
            " tooling (pytest, ruff, etc.)"
        )

    def test_pyproject_targets_python_311(self) -> None:
        meta = _load_pyproject()
        # Some Poetry projects still write [tool.poetry.dependencies] alongside PEP 621
        poetry_deps = (
            meta.get("tool", {}).get("poetry", {}).get("dependencies", {})
        )
        py = poetry_deps.get("python", "")
        assert py.startswith("^3.11") or py.startswith("~3.11") or py.startswith(
            ">=3.11"
        ), f"[tool.poetry.dependencies].python must pin 3.11+, got {py!r}"

    def test_pyproject_lists_pytest_as_dev_dependency(self) -> None:
        meta = _load_pyproject()
        # dev group may appear under [tool.poetry.group.dev.dependencies] or
        # PEP 735 [dependency-groups.dev]
        poetry_groups = (
            meta.get("tool", {}).get("poetry", {}).get("group", {})
        )
        dev_deps = {}
        for grp in poetry_groups.values():
            dev_deps.update(grp.get("dependencies", {}))
        dep_groups = meta.get("dependency-groups", {})
        pytest_present = "pytest" in dev_deps
        if not pytest_present:
            for grp_deps in dep_groups.values():
                if isinstance(grp_deps, list):
                    for entry in grp_deps:
                        if entry.split(";")[0].split("==")[0].split(">=")[0].strip() == "pytest":
                            pytest_present = True
                            break
                if pytest_present:
                    break

        assert (
            pytest_present
        ), "pytest must be declared in the dev/test dependency group"

    def test_pyproject_has_setuptools_build_backend(self) -> None:
        meta = _load_pyproject()
        build_backend = meta.get("build-system", {}).get("build-backend", "")
        # P1-01 ships Poetry-managed layout; backend may be poetry-core or hatchling
        assert build_backend in {
            "poetry.core.masonry.api",
            "poetry.core.masonry.builders.api",
            "hatchling.build",
            "setuptools.build_meta",
            "pdm.backend",
        }, f"unsupported build backend: {build_backend!r}"

    def test_pyproject_lists_ruff_as_dev_dependency(self) -> None:
        meta = _load_pyproject()
        poetry_groups = (
            meta.get("tool", {}).get("poetry", {}).get("group", {})
        )
        dev_deps = {}
        for grp in poetry_groups.values():
            dev_deps.update(grp.get("dependencies", {}))
        assert (
            "ruff" in dev_deps
        ), "ruff must be declared in the dev dependency group"

    def test_pyproject_lists_pyright_as_dev_dependency(self) -> None:
        meta = _load_pyproject()
        poetry_groups = (
            meta.get("tool", {}).get("poetry", {}).get("group", {})
        )
        dev_deps = {}
        for grp in poetry_groups.values():
            dev_deps.update(grp.get("dependencies", {}))
        assert (
            "pyright" in dev_deps
        ), "pyright must be declared in the dev dependency group"


class TestPackageIsImportable:
    """After install, `import job_board_scraper` must succeed."""

    @pytest.mark.skipif(
        not (PROJECT_ROOT / "src").exists()
        and not any((PROJECT_ROOT / p).exists() for p in ("src", "job_board_scraper")),
        reason="package layout not yet created (P1-02 dependency)",
    )
    def test_package_import_smoke(self) -> None:
        try:
            import job_board_scraper  # noqa: F401
        except ImportError as exc:
            pytest.fail(
                f"`import job_board_scraper` must succeed after install: {exc}"
            )


class TestLockfile:
    """`poetry.lock` is required for reproducible installs per P1-01."""

    def test_lockfile_exists(self) -> None:
        lock = PROJECT_ROOT / "poetry.lock"
        assert (
            lock.exists()
        ), "poetry.lock must exist alongside pyproject.toml (P1-01 gate)"

    def test_lockfile_is_not_empty(self) -> None:
        lock = PROJECT_ROOT / "poetry.lock"
        if not lock.exists():
            pytest.skip("poetry.lock missing; covered by test_lockfile_exists")
        assert (
            lock.stat().st_size > 100
        ), "poetry.lock looks empty; re-run `poetry lock`"
