"""RaySim CLI entry point.

Phase A wires the ``run`` subcommand (MVP_STEPS §A.6); Stage B subcommands
land alongside in their own modules.
"""

from __future__ import annotations

import contextlib
import os
import sys

if sys.platform == "win32":
    _env_root = os.path.dirname(sys.executable)
    _dll_path = os.path.join(_env_root, "Library", "bin")
    if os.path.isdir(_dll_path):
        # Mesa's opengl32.dll (from conda mesalib) shadows the system GPU
        # driver when loaded from the same directory as OCCT's TKOpenGl.dll.
        # Rename it so the system AMD/NVIDIA driver is used instead.
        _mesa_gl = os.path.join(_dll_path, "opengl32.dll")
        _mesa_bak = _mesa_gl + ".mesa-backup"
        if os.path.isfile(_mesa_gl) and not os.path.isfile(_mesa_bak):
            with contextlib.suppress(OSError):
                os.rename(_mesa_gl, _mesa_bak)
        os.add_dll_directory(_dll_path)
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
@click.argument("step_path", type=click.Path(exists=True))
@click.option("--accept-warnings", is_flag=True, help="Downgrade warnings to exit 0.")
@click.option("--json-out", type=click.Path(), default=None, help="Write full report as JSON.")
def validate(step_path: str, accept_warnings: bool, json_out: str | None) -> None:
    """Run the full overlap/interference diagnostic on a STEP file."""
    import json

    from raysim.geom.healing import heal_assembly
    from raysim.geom.overlap import OverlapStatus, diagnose_overlaps
    from raysim.geom.step_loader import iter_leaves, load_step
    from raysim.geom.tessellation import tessellate

    root = load_step(step_path)
    leaves = list(iter_leaves(root))

    tessellated = [tessellate(leaf) for leaf in leaves]
    healed = heal_assembly(tessellated)

    shape_map = {leaf.solid_id: leaf.shape for leaf in leaves}
    report = diagnose_overlaps(healed, shapes=shape_map)

    n_contact = sum(1 for p in report.pairs if p.status == OverlapStatus.CONTACT_ONLY)
    n_nested = sum(1 for p in report.pairs if p.status == OverlapStatus.ACCEPTED_NESTED)
    n_warn = len(report.warnings())
    n_fail = len(report.failed())
    n_mismatch = len(report.mismatched_contacts)

    click.echo(f"Pairs: {len(report.pairs)} total")
    click.echo(f"  contact_only: {n_contact}")
    click.echo(f"  accepted_nested: {n_nested}")
    click.echo(f"  interference_warning: {n_warn}")
    click.echo(f"  interference_fail: {n_fail}")
    click.echo(f"Mismatched contacts: {n_mismatch}")
    click.echo(f"Boolean failures: {len(report.boolean_failures)}")

    if json_out is not None:
        import dataclasses
        from pathlib import Path

        Path(json_out).write_text(
            json.dumps(dataclasses.asdict(report), indent=2, default=str),
            encoding="utf-8",
        )
        click.echo(f"Report written to {json_out}")

    n_bool_fail = len(report.boolean_failures)
    has_issues = n_fail > 0 or n_bool_fail > 0 or (n_warn > 0 and not accept_warnings)
    if has_issues:
        raise SystemExit(1)


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
