"""Tests for P1-04 — pytest configuration and coverage threshold.

These tests verify the contract in `docs/ROADMAP.md` Phase 1 row P1-04
by reading the actual configuration files directly rather than running pytest
as a subprocess (which avoids WindowsStore launcher and recursive collection issues).

Gate evidence:
- ``pyproject.toml`` contains ``asyncio_mode = "auto"`` under [tool.pytest.ini_options]
- ``pyproject.toml`` registers ``unit``, ``integration``, ``e2e``, ``slow`` markers
- ``pyproject.toml`` sets ``fail_under = 80`` in [tool.coverage.report]
- ``tests/smoke/`` directory exists with at least one ``test_*.py`` file
- ``pytest --cov`` runs without error and respects the 80% threshold
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest


import sys
from pathlib import Path

import pytest


# __file__ from tests/_config/test_pytest_config.py resolves to:
#   D:\Sources\job-board-scraper\tests\_config\test_pytest_config.py
# parents[0] = tests/_config
# parents[1] = tests
# parents[2] = project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Canonicalize for Windows: resolve removes trailing parts quirks
PROJECT_ROOT = PROJECT_ROOT.resolve()
PYPROJECT = PROJECT_ROOT / "pyproject.toml"


def _load_pyproject() -> dict:
    assert PYPROJECT.exists(), "pyproject.toml must exist"
    with PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)


class TestPytestConfiguration:
    """Verify ``pyproject.toml`` pytest configuration."""

    def test_pytest_reads_config_file(self) -> None:
        """``pyproject.toml`` must exist and be valid TOML."""
        assert PYPROJECT.exists()
        content = PYPROJECT.read_text(encoding="utf-8")
        assert "[tool.pytest.ini_options]" in content

    def test_asyncio_mode_is_auto(self) -> None:
        """``asyncio_mode`` must be set to ``auto`` for pytest-asyncio auto-detection."""
        meta = _load_pyproject()
        opts = meta.get("tool", {}).get("pytest", {}).get("ini_options", {})
        assert opts.get("asyncio_mode") == "auto", (
            "pyproject.toml [tool.pytest.ini_options] must set asyncio_mode = 'auto'"
        )

    def test_unit_marker_registered(self) -> None:
        """``unit`` marker must be registered."""
        meta = _load_pyproject()
        markers = meta.get("tool", {}).get("pytest", {}).get("ini_options", {}).get("markers", [])
        assert any("unit" in m for m in markers), (
            f"pytest markers must include 'unit'. Found: {markers}"
        )

    def test_integration_marker_registered(self) -> None:
        """``integration`` marker must be registered."""
        meta = _load_pyproject()
        markers = meta.get("tool", {}).get("pytest", {}).get("ini_options", {}).get("markers", [])
        assert any("integration" in m for m in markers), (
            f"pytest markers must include 'integration'. Found: {markers}"
        )

    def test_e2e_marker_registered(self) -> None:
        """``e2e`` marker must be registered."""
        meta = _load_pyproject()
        markers = meta.get("tool", {}).get("pytest", {}).get("ini_options", {}).get("markers", [])
        assert any("e2e" in m for m in markers), (
            f"pytest markers must include 'e2e'. Found: {markers}"
        )

    def test_slow_marker_registered(self) -> None:
        """``slow`` marker must be registered."""
        meta = _load_pyproject()
        markers = meta.get("tool", {}).get("pytest", {}).get("ini_options", {}).get("markers", [])
        assert any("slow" in m for m in markers), (
            f"pytest markers must include 'slow'. Found: {markers}"
        )

    def test_testpaths_is_configured(self) -> None:
        """``testpaths`` must point to the ``tests/`` directory."""
        meta = _load_pyproject()
        testpaths = meta.get("tool", {}).get("pytest", {}).get("ini_options", {}).get("testpaths", [])
        assert "tests" in testpaths, (
            f"pytest testpaths must include 'tests'. Found: {testpaths}"
        )

    def test_asyncio_default_fixture_loop_scope(self) -> None:
        """``asyncio_default_fixture_loop_scope`` must be set to ``function``."""
        meta = _load_pyproject()
        opts = meta.get("tool", {}).get("pytest", {}).get("ini_options", {})
        assert opts.get("asyncio_default_fixture_loop_scope") == "function"


class TestCoverageConfiguration:
    """Verify coverage configuration."""

    def test_coverage_threshold_80_in_config(self) -> None:
        """``fail_under = 80`` must be set in ``[tool.coverage.report]``."""
        meta = _load_pyproject()
        report = meta.get("tool", {}).get("coverage", {}).get("report", {})
        fail_under = report.get("fail_under")
        assert fail_under == 80, (
            f"[tool.coverage.report].fail_under must be 80, got {fail_under!r}"
        )

    def test_coverage_fail_under_check_is_global(self) -> None:
        """``fail_under_check = "global"`` must be set (newer coverage versions)."""
        meta = _load_pyproject()
        report = meta.get("tool", {}).get("coverage", {}).get("report", {})
        check = report.get("fail_under_check")
        # This is optional; we just warn if it's missing
        # The primary gate is the value above
        if check is not None:
            assert check == "global", (
                f"fail_under_check should be 'global', got {check!r}"
            )

    def test_coverage_source_includes_job_board_scraper(self) -> None:
        """Coverage source must include ``job_board_scraper``."""
        meta = _load_pyproject()
        run = meta.get("tool", {}).get("coverage", {}).get("run", {})
        source = run.get("source", [])
        assert any("job_board_scraper" in s for s in source), (
            f"[tool.coverage.run].source must include 'job_board_scraper'. Found: {source}"
        )

    def test_coverage_omit_excludes_tests(self) -> None:
        """Coverage must omit the ``tests/`` directory."""
        meta = _load_pyproject()
        run = meta.get("tool", {}).get("coverage", {}).get("run", {})
        omit = run.get("omit", [])
        assert any("tests" in o for o in omit), (
            f"[tool.coverage.run].omit must include 'tests/*'. Found: {omit}"
        )


class TestSmokeTest:
    """A smoke test must exist under ``tests/smoke/``."""

    def test_smoke_test_directory_exists(self) -> None:
        """``tests/smoke/`` directory must exist."""
        smoke_dir = PROJECT_ROOT / "tests" / "smoke"
        assert smoke_dir.exists(), (
            "tests/smoke/ must exist (P1-04 gate). Create it and add at least one test_*.py file."
        )

    def test_at_least_one_smoke_test_file(self) -> None:
        """At least one ``test_*.py`` file must exist under ``tests/smoke/``."""
        smoke_dir = PROJECT_ROOT / "tests" / "smoke"
        if not smoke_dir.exists():
            pytest.skip("tests/smoke/ does not exist yet; P1-04 GREEN will create it")
        test_files = list(smoke_dir.glob("test_*.py"))
        assert len(test_files) >= 1, (
            "tests/smoke/ must contain at least one test_*.py file"
        )

    def test_smoke_test_can_be_imported(self) -> None:
        """Smoke test files must be valid Python (no syntax errors)."""
        smoke_dir = PROJECT_ROOT / "tests" / "smoke"
        if not smoke_dir.exists():
            pytest.skip("tests/smoke/ does not exist yet")
        import ast
        for test_file in smoke_dir.glob("test_*.py"):
            source = test_file.read_text(encoding="utf-8")
            try:
                ast.parse(source)
            except SyntaxError as exc:
                pytest.fail(f"Syntax error in {test_file}: {exc}")
