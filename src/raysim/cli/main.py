"""RaySim CLI entry point.

Phase A wires the ``run`` subcommand (MVP_STEPS §A.6); Stage B subcommands
land alongside in their own modules.
"""

from __future__ import annotations

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


if __name__ == "__main__":
    main()
