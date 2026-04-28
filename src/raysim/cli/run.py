"""``raysim run`` subcommand — Phase A.6.

End-to-end Stage A driver: turn (scene STL directory + materials CSV/YAML +
detectors JSON + OMERE ``.dos``) into a canonical ``run.json``.

Determinism (MVP_PLAN §1, MVP_STEPS §A.6):
  * Detectors are processed in *input order* and emitted in the same order.
  * HEALPix pixels are summed in index order (the stride loop in
    :mod:`raysim.ray.tracer` is monotonic in pixel id).
  * Output is canonical JSON: sorted keys, ``%.17g`` floats, no timestamps in
    the deterministic stream. A separate ``human_metadata`` block (excluded
    from the deterministic hash) is written alongside if requested.

Materials schema (CSV columns; first row is header):

    group_id, density_g_cm3, z_eff, display_name

Or YAML form (preferred for libraries with composition):

    materials:
      - group_id: aluminum
        density_g_cm3: 2.70
        z_eff: 13.0
        display_name: Al 6061
      - ...

Detectors JSON:

    {"detectors": [{"name": "...", "position_xyz_mm": [x, y, z]}, ...]}

or a top-level list of the same dicts.
"""

from __future__ import annotations

import contextlib
import csv
import json
import platform
from datetime import UTC
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import click
import structlog
import yaml

from raysim import __version__
from raysim.dose import build_dose_spline
from raysim.dose.aggregator import aggregate_detector
from raysim.env.importers.omere_dos import import_omere_dos
from raysim.proj.canonical_json import dumps as canonical_dumps
from raysim.proj.hashing import hash_canonical, hash_files
from raysim.proj.schema import (
    Detector,
    Material,
    MaterialAssignment,
    Provenance,
    RunResult,
)
from raysim.ray.scene import load_scene_from_directory

_LOG = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def _load_materials(path: Path) -> list[Material]:
    if path.suffix.lower() in {".yaml", ".yml"}:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        entries = data["materials"] if isinstance(data, dict) and "materials" in data else data
        return [Material.model_validate(e) for e in entries]

    # CSV path.
    materials: list[Material] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            materials.append(
                Material(
                    group_id=row["group_id"].strip(),
                    density_g_cm3=float(row["density_g_cm3"]),
                    z_eff=float(row["z_eff"]) if row.get("z_eff") else None,
                    display_name=(row.get("display_name") or "").strip(),
                )
            )
    return materials


def _load_detectors(path: Path) -> list[Detector]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "detectors" in raw:
        entries = raw["detectors"]
    elif isinstance(raw, list):
        entries = raw
    else:
        raise ValueError(f"detectors JSON must be a list or {{detectors: [...]}}; got {type(raw)}")
    return [Detector.model_validate(e) for e in entries]


def _load_assignments(path: Path | None) -> list[MaterialAssignment]:
    """Return the ``MaterialAssignment[]`` from ``path``, or ``[]`` if no
    assignments file was supplied. The empty-list case is *distinct* from a
    file with an empty list — both hash to the same canonical-empty value, so
    "no assignments" is recoverable from provenance."""
    if path is None:
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries = raw.get("assignments", raw) if isinstance(raw, dict) else raw
    return [MaterialAssignment.model_validate(e) for e in entries]


# ---------------------------------------------------------------------------
# Provenance helpers
# ---------------------------------------------------------------------------


_KEY_LIBRARIES = (
    "numpy",
    "scipy",
    "trimesh",
    "embreex",
    "healpy",
    "pydantic",
    "click",
    "structlog",
)


def _library_versions() -> dict[str, str]:
    out: dict[str, str] = {}
    for name in _KEY_LIBRARIES:
        with contextlib.suppress(PackageNotFoundError):
            out[name] = version(name)
    return out


def _scene_geometry_hash(scene_dir: Path) -> str:
    stl_paths = sorted(scene_dir.glob("*.stl"))
    if not stl_paths:
        raise FileNotFoundError(f"no STLs in scene directory: {scene_dir}")
    return hash_files({p.name: p for p in stl_paths})


def _materials_hash(materials: list[Material]) -> str:
    return hash_canonical([m.model_dump() for m in materials])


def _detectors_hash(detectors: list[Detector]) -> str:
    return hash_canonical([d.model_dump() for d in detectors])


def _assignments_hash(assignments: list[MaterialAssignment]) -> str:
    """Hash the assignment list in the order the user provided it. Order is
    irrelevant to the engine (the loader builds a dict), but stable hashing
    means re-saving the same project doesn't churn provenance."""
    return hash_canonical([a.model_dump() for a in assignments])


def _dose_curve_hash(path: Path) -> str:
    # Hash the source bytes; downstream importers are pure functions, so the
    # source is the canonical artifact.
    from raysim.proj.hashing import hash_file

    return hash_file(path)


# ---------------------------------------------------------------------------
# CLI command
# ---------------------------------------------------------------------------


@click.command()
@click.option(
    "--scene",
    "scene_dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    required=True,
    help="Directory of STL files; one file per material group_id.",
)
@click.option(
    "--materials",
    "materials_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="Material library — CSV or YAML.",
)
@click.option(
    "--detectors",
    "detectors_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="Detectors JSON.",
)
@click.option(
    "--dose-curve",
    "dose_curve_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="Solid-sphere dose-depth curve (OMERE .dos).",
)
@click.option(
    "--assignments",
    "assignments_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Optional MaterialAssignment[] JSON. If omitted, solid_id == material_group_id.",
)
@click.option("--nside", type=int, default=64, show_default=True, help="HEALPix Nside.")
@click.option(
    "--out",
    "output_path",
    type=click.Path(dir_okay=False, path_type=Path),
    required=True,
    help="Output run.json path.",
)
@click.option(
    "--emit-pixel-map/--no-emit-pixel-map",
    default=False,
    help="Include the full per-pixel mm-Al-equivalent map in the output.",
)
@click.option(
    "--human-metadata-out",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help=(
        "Optional sibling file for non-deterministic provenance "
        "(timestamps, hostname). Excluded from the canonical run.json."
    ),
)
def run(
    scene_dir: Path,
    materials_path: Path,
    detectors_path: Path,
    dose_curve_path: Path,
    assignments_path: Path | None,
    nside: int,
    output_path: Path,
    emit_pixel_map: bool,
    human_metadata_out: Path | None,
) -> None:
    """Run a Stage A scenario and emit a canonical ``run.json``.

    Bit-identical determinism applies to ``run.json`` only; human-facing
    artifacts (logs, optional ``human_metadata``) include timestamps and are
    not bit-identical (MVP_PLAN §1).
    """
    materials = _load_materials(materials_path)
    detectors = _load_detectors(detectors_path)
    assignments = _load_assignments(assignments_path)

    # Empty list ⇒ ``solid_id == material_group_id`` fallback in the loader.
    scene = load_scene_from_directory(
        scene_dir, materials, assignments if assignments else None
    )
    ddc = import_omere_dos(dose_curve_path)
    spline = build_dose_spline(ddc)

    detector_results = []
    for detector in detectors:
        res = aggregate_detector(
            scene, spline, detector, nside=nside, emit_pixel_map=emit_pixel_map
        )
        detector_results.append(res)
        _LOG.info(
            "cli.detector_complete",
            name=detector.name,
            mm_al_mean=res.mm_al_equivalent_mean,
            dose_total_krad=res.dose_total_krad,
            n_stack_leak=res.n_stack_leak_rays,
        )

    epsilon_mm = 1e-6 * scene.bbox_diag_mm
    provenance = Provenance(
        raysim_version=__version__,
        library_versions=_library_versions(),
        nside=nside,
        epsilon_mm=epsilon_mm,
        bbox_diag_mm=scene.bbox_diag_mm,
        geometry_hash=_scene_geometry_hash(scene_dir),
        materials_hash=_materials_hash(materials),
        assignments_hash=_assignments_hash(assignments),
        detectors_hash=_detectors_hash(detectors),
        dose_curve_hash=_dose_curve_hash(dose_curve_path),
    )

    run_result = RunResult(detectors=tuple(detector_results), provenance=provenance)

    # Run-fatal: any ray hit the safety cap.
    n_max_hit = sum(d.n_max_hit_rays for d in detector_results)
    if n_max_hit:
        raise click.ClickException(
            f"{n_max_hit} ray(s) exceeded the per-ray hit safety cap "
            "(see ray.tracer.max_hits_exceeded in the log). Run is fatal."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(canonical_dumps(run_result), encoding="utf-8")

    if human_metadata_out:
        from datetime import datetime

        human: dict[str, Any] = {
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "python": platform.python_version(),
            },
            "input_paths": {
                "scene_dir": str(scene_dir.resolve()),
                "materials": str(materials_path.resolve()),
                "detectors": str(detectors_path.resolve()),
                "dose_curve": str(dose_curve_path.resolve()),
            },
        }
        human_metadata_out.parent.mkdir(parents=True, exist_ok=True)
        human_metadata_out.write_text(canonical_dumps(human), encoding="utf-8")

    click.echo(f"wrote {output_path}")
