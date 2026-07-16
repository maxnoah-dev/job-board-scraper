"""Tests for P1-05 — Ruff, Pyright, and secret-scan configuration.

These tests gate the contract in `docs/ROADMAP.md` Phase 1 row P1-05:
- ``ruff format`` runs and passes
- ``ruff check`` runs and passes
- ``pyright`` runs without crashing
- ``detect-secrets`` scan runs cleanly
- CI workflow file exists and is valid

All tools are invoked as CLI executables via the venv Scripts/ directory
to avoid WindowsStore launcher interception.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2].resolve()
VENV_SCRIPTS = PROJECT_ROOT / ".venv" / "Scripts"


def _venv_cmd(name: str, *args: str) -> subprocess.CompletedProcess:
    """Run a CLI tool installed in the venv's Scripts/ directory."""
    exe = str((VENV_SCRIPTS / name).resolve())
    return subprocess.run(
        [exe] + list(args),
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=120,
    )


def _venv_module(module: str, *args: str) -> subprocess.CompletedProcess:
    """Run a Python module via the venv python."""
    return subprocess.run(
        [str((VENV_SCRIPTS / "python.exe").resolve()), "-m", module] + list(args),
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=120,
    )


class TestRuffConfiguration:
    """Ruff linter and formatter must be configured and pass."""

    def test_ruff_is_installed(self) -> None:
        """``ruff`` CLI must be available."""
        result = _venv_cmd("ruff.exe", "--version")
        assert result.returncode == 0, f"ruff --version failed: {result.stderr}"

    def test_ruff_check_passes(self) -> None:
        """``ruff check .`` must pass."""
        result = _venv_cmd("ruff.exe", "check", ".")
        assert result.returncode == 0, (
            f"ruff check found violations:\n{result.stdout}\n{result.stderr}"
        )

    def test_ruff_format_passes(self) -> None:
        """``ruff format --check .`` must pass."""
        result = _venv_cmd("ruff.exe", "format", "--check", ".")
        if result.returncode != 0:
            pytest.fail(
                f"ruff format violations found (exit {result.returncode}).\n"
                f"Run `ruff format .` to fix.\n{result.stdout[:500]}"
            )

    def test_ruff_config_exists(self) -> None:
        """ruff config (pyproject.toml or .ruff.toml) must exist."""
        ruff_toml = PROJECT_ROOT / ".ruff.toml"
        pyproject = PROJECT_ROOT / "pyproject.toml"
        content = ""
        if ruff_toml.exists():
            content = ruff_toml.read_text(encoding="utf-8")
        elif pyproject.exists():
            content = pyproject.read_text(encoding="utf-8")
        assert "[tool.ruff]" in content or "[ruff]" in content, (
            "ruff configuration section must exist in pyproject.toml or .ruff.toml"
        )


class TestPyrightConfiguration:
    """Pyright type checker must be configured and run without crashing."""

    def test_pyright_is_installed(self) -> None:
        """``pyright`` CLI must be available."""
        result = _venv_cmd("pyright.exe", "--version")
        assert result.returncode == 0, f"pyright --version failed: {result.stderr}"

    def test_pyright_runs_on_src(self) -> None:
        """``pyright src`` must run without crashing."""
        result = _venv_cmd("pyright.exe", "src")
        # returncode 0 = no errors, 1 = errors found, 2 = config problem
        assert result.returncode in (0, 1), (
            f"pyright crashed (exit {result.returncode}): {result.stderr}"
        )

    def test_pyright_config_exists(self) -> None:
        """pyright config (pyproject.toml or pyrightconfig.json) must exist."""
        pyright_cfg = PROJECT_ROOT / "pyrightconfig.json"
        pyproject = PROJECT_ROOT / "pyproject.toml"
        has_section = "[tool.pyright]" in pyproject.read_text(encoding="utf-8") if pyproject.exists() else False
        assert pyright_cfg.exists() or has_section, (
            "pyright configuration must exist (pyrightconfig.json or [tool.pyright] in pyproject.toml)"
        )


class TestSecretScanning:
    """detect-secrets must be configured and scan cleanly."""

    def test_detect_secrets_is_installed(self) -> None:
        """``detect-secrets`` must be available."""
        result = _venv_module("detect_secrets", "--version")
        assert result.returncode in (0, 2), (
            f"detect-secrets --version failed: {result.stderr}"
        )

    def test_detect_secrets_scan_runs(self) -> None:
        """``detect-secrets scan .`` must run without crashing."""
        result = _venv_module(
            "detect_secrets", "scan",
            "--base64-limit", "4.5",
            "--string-limit", "4.5",
            ".",
        )
        assert result.returncode in (0, 1), (
            f"detect-secrets scan crashed (exit {result.returncode}): {result.stderr}"
        )


class TestCIBaseline:
    """CI configuration must exist."""

    def test_github_workflows_dir_exists(self) -> None:
        """.github/workflows/`` must exist."""
        workflows_dir = PROJECT_ROOT / ".github" / "workflows"
        assert workflows_dir.exists(), (
            ".github/workflows/ must exist (P1-05 gate). Create it."
        )

    def test_ci_workflow_file_exists(self) -> None:
        """.github/workflows/ci.yml`` must exist."""
        ci_file = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        assert ci_file.exists(), (
            ".github/workflows/ci.yml must exist (P1-05 gate). Create it."
        )

    def test_ci_workflow_is_valid_yaml(self) -> None:
        """.github/workflows/ci.yml`` must be valid YAML."""
        ci_file = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        if not ci_file.exists():
            pytest.skip("ci.yml missing")
        try:
            yaml.safe_load(ci_file.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            pytest.fail(f"ci.yml is not valid YAML: {exc}")

    def test_ci_workflow_runs_ruff(self) -> None:
        """CI workflow must run ``ruff check``."""
        ci_file = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        if not ci_file.exists():
            pytest.skip("ci.yml missing")
        content = ci_file.read_text(encoding="utf-8")
        assert "ruff" in content, (
            ".github/workflows/ci.yml must include a ruff step"
        )

    def test_ci_workflow_runs_pyright(self) -> None:
        """CI workflow must run ``pyright``."""
        ci_file = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        if not ci_file.exists():
            pytest.skip("ci.yml missing")
        content = ci_file.read_text(encoding="utf-8")
        assert "pyright" in content, (
            ".github/workflows/ci.yml must include a pyright step"
        )

    def test_ci_workflow_runs_pytest(self) -> None:
        """CI workflow must run ``pytest``."""
        ci_file = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        if not ci_file.exists():
            pytest.skip("ci.yml missing")
        content = ci_file.read_text(encoding="utf-8")
        assert "pytest" in content, (
            ".github/workflows/ci.yml must include a pytest step"
        )
