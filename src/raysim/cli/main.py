"""RaySim CLI entry point.

Phase A wires the ``run`` subcommand (MVP_STEPS §A.6); Stage B subcommands
land alongside in their own modules.
"""

from __future__ import annotations

import os
import platform
import sys

if platform.system() == "Windows":
    _env_root = os.path.dirname(sys.executable)
    _dll_path = os.path.join(_env_root, "Library", "bin")
    if os.path.isdir(_dll_path):
        os.add_dll_directory(_dll_path)  # type: ignore[attr-defined]
        os.environ["PATH"] = _dll_path + ";" + os.environ.get("PATH", "")

import click

from raysim import __version__
from raysim.cli.run import run as run_cmd


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="raysim")
@click.pass_context
def main(ctx: click.Context) -> None:
    """RaySim — 3D TID sector-shielding simulator."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


main.add_command(run_cmd)


@main.command()
def gui() -> None:
    """Launch the RaySim desktop application."""
    try:
        from raysim.ui.app import launch
    except ImportError as exc:
        raise click.ClickException(
            "PySide6 not installed. Install with: uv sync --extra ui"
        ) from exc
    launch()


if __name__ == "__main__":
    main()
