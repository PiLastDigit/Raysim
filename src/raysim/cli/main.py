"""RaySim CLI entry point.

Phase 0: stub with `--version`. Phase A wires the real `run` command per
MVP_STEPS.md §A.6.
"""

from __future__ import annotations

import click

from raysim import __version__


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="raysim")
@click.pass_context
def main(ctx: click.Context) -> None:
    """RaySim — 3D TID sector-shielding simulator."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


if __name__ == "__main__":
    main()
