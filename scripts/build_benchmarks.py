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


def _hollow_shell(outer: trimesh.Trimesh, inner: trimesh.Trimesh) -> trimesh.Trimesh:
    """Return a single mesh representing a hollow solid: ``outer`` with ``inner``
    as a cavity. Inner-shell normals are flipped so they point *out of solid
    material* into the cavity void, per ``MVP_STEPS.md`` §B1.3 convention.

    Watertightness: each sub-shell stays closed independently. The two shells
    must be disjoint (inner strictly contained in outer) — the caller is
    responsible for that.
    """
    inner = inner.copy()
    inner.invert()
    return trimesh.util.concatenate([outer, inner])


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
    """Solid 50 mm-radius Al sphere.

    Use ``uv_sphere`` so the ±Z poles are *exact* mesh vertices — the principal-
    axis ray then has zero discretization error and the analytic chord
    ``2R = 100 mm`` is reproducible to ≤1e-5. Off-axis rays through any
    triangulated sphere have O(edge_len²/R) sagitta error and are not part of
    the 1e-5 acceptance set; ``analytic_targets.yaml`` only documents the
    pole-aligned ray for this fixture.
    """
    out = GEOM_DIR / "solid_sphere"
    sphere = trimesh.creation.uv_sphere(radius=50.0, count=[64, 64])
    p = out / "aluminum.stl"
    _write_stl(sphere, p)
    _emit_manifest(out, {"aluminum": p})


def build_concentric_shell() -> None:
    """Hollow Al shell (R=20→50) enclosing a solid Cu sphere (R=20).

    The Al mesh is one solid with two closed sub-shells: outer R=50 (normals
    outward) + inner cavity R=20 (normals inward into cavity void), per the
    cavity convention in ``MVP_STEPS.md`` §B1.3. The Cu sphere occupies the
    cavity, so the inner Al cavity face and the Cu outer face are *coincident*
    at R=20 — by design. This is the canonical test fixture for A.4's
    tied-batch / B1.5's ``contact_only`` pair classification: the principal
    axis ray accumulates 60 mm Al + 40 mm Cu cleanly when the accumulator
    handles the tie.

    Use ``uv_sphere`` so all four pole crossings (±Z on R=20 and R=50) are
    exact mesh vertices, eliminating discretization error on the analytic
    center-ray test.
    """
    out = GEOM_DIR / "concentric_shell"
    al_outer = trimesh.creation.uv_sphere(radius=50.0, count=[64, 64])
    al_inner = trimesh.creation.uv_sphere(radius=20.0, count=[64, 64])
    al = _hollow_shell(al_outer, al_inner)
    cu = trimesh.creation.uv_sphere(radius=20.0, count=[64, 64])
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

    Layout (mm), all centered on the box origin:
      * Outer aluminum box — 200 mm cube, **2 mm wall thickness** (true hollow shell:
        outer 200 mm + inner 196 mm cavity, normals on the cavity face inward
        per ``MVP_STEPS.md`` §B1.3). A center-of-face ray traverses 2 mm Al,
        then any internal components, then 2 mm Al on exit — *not* 200 mm of
        solid Al.
      * FR4 PCB inside — 150×100×1.6, lying 5 mm above the inner box floor.
      * Battery (modelled as Cu) — 60×40×20 sitting on the PCB.
      * Solar panel (GaAs) — 200×200×0.5 on the outside +Z face.

    Each material group lives in its own STL.
    """
    out = ASM_DIR / "custom_test_article"

    # Outer Al box: 200 mm cube. Wall thickness = 2 mm → inner cavity 196 mm.
    al_outer = trimesh.creation.box(extents=[200.0, 200.0, 200.0])
    al_inner = trimesh.creation.box(extents=[196.0, 196.0, 196.0])
    al_box = _hollow_shell(al_outer, al_inner)

    # FR4 PCB. Inner box floor sits at -98 mm; PCB rests 5 mm above that.
    pcb = trimesh.creation.box(extents=[150.0, 100.0, 1.6])
    pcb.apply_translation([0.0, 0.0, -98.0 + 5.0 + 0.8])

    # Battery (Cu). Sits on top of PCB.
    batt = trimesh.creation.box(extents=[60.0, 40.0, 20.0])
    batt.apply_translation([0.0, 0.0, -98.0 + 5.0 + 1.6 + 10.0])

    # Solar panel (GaAs) outside +Z face.
    panel = trimesh.creation.box(extents=[200.0, 200.0, 0.5])
    panel.apply_translation([0.0, 0.0, 100.0 + 0.25])

    files: dict[str, Path] = {}
    meshes: list[tuple[str, trimesh.Trimesh]] = [
        ("aluminum", al_box),
        ("fr4", pcb),
        ("copper", batt),
        ("gaas", panel),
    ]
    for name, mesh in meshes:
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
