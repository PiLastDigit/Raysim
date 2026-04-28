"""Phase 0 smoke: `raysim --version` prints, package imports."""

from __future__ import annotations

from click.testing import CliRunner

import raysim
from raysim.cli.main import main


def test_package_version_present() -> None:
    assert isinstance(raysim.__version__, str)
    assert raysim.__version__


def test_cli_version_runs() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert raysim.__version__ in result.output


def test_cli_help_runs() -> None:
    runner = CliRunner()
    result = runner.invoke(main, [])
    assert result.exit_code == 0
    assert "raysim" in result.output.lower()
