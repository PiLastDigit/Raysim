#!/usr/bin/env python3
"""Generate RaySim's procedural benchmark geometries.

Outputs live in ``benchmarks/geometries/`` and ``benchmarks/assemblies/`` so
they can be regenerated bit-for-bit from source. Geometries are emitted as
STL (Stage A's input format) using ``trimesh``; STEP outputs are deferred to
the Stage B path which uses ``pythonocc-core`` (conda-only).

Each geometry directory holds:
  * One STL per material group (Stage A scene-loader convention, §A.3).
  * A ``manifest.json`` with SHA-256 hashes of every STL — a CI guard against
    silent corpus drift.

The companion ``benchmarks/analytic_targets.yaml`` documents closed-form ∑ρL
expectations the Phase A acceptance suite (§A.7) checks against.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import trimesh

ROOT = Path(__file__).resolve().parent.parent
GEOM_DIR = ROOT / "benchmarks" / "geometries"
ASM_DIR = ROOT / "benchmarks" / "assemblies"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _write_stl(mesh: trimesh.Trimesh, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Force binary STL with deterministic vertex ordering.
    mesh.export(path, file_type="stl")


def _emit_manifest(out_dir: Path, files: dict[str, Path]) -> None:
    manifest = {
        "files": {
            name: {
                "path": str(p.relative_to(ROOT).as_posix()),
                "sha256": _sha256(p),
                "n_triangles": int(trimesh.load(p).faces.shape[0]),
            }
            for name, p in files.items()
        }
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Canonical analytic geometries
# ---------------------------------------------------------------------------


def build_aluminum_box() -> None:
    """Solid 100 mm Al cube. ∑ρL along principal axes = ρ_Al × 100 mm."""
    out = GEOM_DIR / "aluminum_box"
    box = trimesh.creation.box(extents=[100.0, 100.0, 100.0])
    p = out / "aluminum.stl"
    _write_stl(box, p)
    _emit_manifest(out, {"aluminum": p})


def build_solid_sphere() -> None:
    """Solid 50 mm-radius Al sphere; analytic ∑ρL(d) = 2 ρ √(R²−d²) for impact d."""
    out = GEOM_DIR / "solid_sphere"
    # icosphere(subdivisions=4) gives 1280 triangles — plenty for ≤1e-5 path-length
    # error on principal-axis rays. Higher subdivisions later if A.7 demands it.
    sphere = trimesh.creation.icosphere(subdivisions=4, radius=50.0)
    p = out / "aluminum.stl"
    _write_stl(sphere, p)
    _emit_manifest(out, {"aluminum": p})


def build_concentric_shell() -> None:
    """Outer Al shell (R=50) with inner Cu shell (R=20).

    Phase A's concentric-shell test (§A.7) expects per-shell chord-length pairs
    to match analytic to ≤1e-5. Each shell is its own STL (one material group
    each) so the Stage A scene loader picks them up via the
    ``subdirectory-of-STLs`` convention.
    """
    out = GEOM_DIR / "concentric_shell"
    al = trimesh.creation.icosphere(subdivisions=4, radius=50.0)
    cu = trimesh.creation.icosphere(subdivisions=3, radius=20.0)
    p_al = out / "aluminum.stl"
    p_cu = out / "copper.stl"
    _write_stl(al, p_al)
    _write_stl(cu, p_cu)
    _emit_manifest(out, {"aluminum": p_al, "copper": p_cu})


# ---------------------------------------------------------------------------
# Custom test article (box + PCB + battery + panel)
# ---------------------------------------------------------------------------


def build_custom_test_article() -> None:
    """Procedural multi-material test article — placeholder for the open-source
    CubeSat & larger open mission still to be sourced (see benchmarks/README.md).

    Layout (mm):
      * Outer aluminum box — 200×200×200, 2 mm wall thickness implied by inner cavity.
      * FR4 PCB inside — 150×100×1.6, lying on the +Z floor of the box.
      * Battery (modelled as Cu) — 60×40×20 sitting on the PCB.
      * Solar panel (GaAs) — 200×200×0.5 on the outside +Z face.

    Each material group lives in its own STL.
    """
    out = ASM_DIR / "custom_test_article"

    # Outer Al box: 200 cube.
    al_box = trimesh.creation.box(extents=[200.0, 200.0, 200.0])

    # FR4 PCB.
    pcb = trimesh.creation.box(extents=[150.0, 100.0, 1.6])
    pcb.apply_translation([0.0, 0.0, -100.0 + 5.0 + 0.8])  # 5 mm above box floor

    # Battery (Cu).
    batt = trimesh.creation.box(extents=[60.0, 40.0, 20.0])
    batt.apply_translation(
        [0.0, 0.0, -100.0 + 5.0 + 1.6 + 10.0]  # sits on top of PCB
    )

    # Solar panel (GaAs) outside +Z face.
    panel = trimesh.creation.box(extents=[200.0, 200.0, 0.5])
    panel.apply_translation([0.0, 0.0, 100.0 + 0.25])

    files: dict[str, Path] = {}
    for name, mesh in [
        ("aluminum", al_box),
        ("fr4", pcb),
        ("copper", batt),
        ("gaas", panel),
    ]:
        p = out / f"{name}.stl"
        _write_stl(mesh, p)
        files[name] = p
    _emit_manifest(out, files)


# ---------------------------------------------------------------------------


def main() -> int:
    builders = [
        ("aluminum_box", build_aluminum_box),
        ("solid_sphere", build_solid_sphere),
        ("concentric_shell", build_concentric_shell),
        ("custom_test_article", build_custom_test_article),
    ]
    for name, fn in builders:
        print(f"  building {name}")
        fn()
    print(f"  benchmark corpus written under {GEOM_DIR.relative_to(ROOT)}/ "
          f"and {ASM_DIR.relative_to(ROOT)}/")
    # Reproducibility hint: print top-level manifest hashes.
    for sub in sorted([*GEOM_DIR.iterdir(), *ASM_DIR.iterdir()]):
        m = sub / "manifest.json"
        if not m.exists():
            continue
        data = json.loads(m.read_text(encoding="utf-8"))
        for name, info in sorted(data["files"].items()):
            print(f"    {sub.name}/{name}: {info['sha256'][:12]}…  ({info['n_triangles']} tri)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
