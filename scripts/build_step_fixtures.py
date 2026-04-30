#!/usr/bin/env python3
"""Generate procedural STEP benchmark fixtures via OCCT primitives.

Outputs live in ``benchmarks/step/``.  Each fixture is a STEP file generated
deterministically from ``BRepPrimAPI_*`` constructors and ``STEPControl_Writer``.
A ``manifest.json`` records per-file SHA-256 hashes.

Requires ``pythonocc-core`` (conda-forge only).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STEP_DIR = ROOT / "benchmarks" / "step"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_step(shape: object, path: Path) -> None:
    from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer

    path.parent.mkdir(parents=True, exist_ok=True)
    writer = STEPControl_Writer()
    writer.Transfer(shape, STEPControl_AsIs)
    writer.Write(str(path))


def _make_box(dx: float, dy: float, dz: float, *, center: bool = True) -> object:
    """Create a box, optionally centered at the origin."""
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCC.Core.gp import gp_Pnt

    if center:
        pnt = gp_Pnt(-dx / 2, -dy / 2, -dz / 2)
        return BRepPrimAPI_MakeBox(pnt, dx, dy, dz).Shape()
    return BRepPrimAPI_MakeBox(dx, dy, dz).Shape()


def _make_sphere(radius: float) -> object:
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeSphere

    return BRepPrimAPI_MakeSphere(radius).Shape()


def _make_cylinder(radius: float, height: float) -> object:
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCylinder

    return BRepPrimAPI_MakeCylinder(radius, height).Shape()


def _translate(shape: object, dx: float, dy: float, dz: float) -> object:
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCC.Core.gp import gp_Trsf, gp_Vec

    trsf = gp_Trsf()
    trsf.SetTranslation(gp_Vec(dx, dy, dz))
    return BRepBuilderAPI_Transform(shape, trsf, True).Shape()


def _make_compound(shapes: list[object]) -> object:
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.TopoDS import TopoDS_Compound

    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    for s in shapes:
        builder.Add(compound, s)
    return compound


def _cut(shape: object, tool: object) -> object:
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut

    return BRepAlgoAPI_Cut(shape, tool).Shape()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def build_aluminum_box() -> Path:
    """100 mm Al cube centered at origin."""
    p = STEP_DIR / "aluminum_box.step"
    _write_step(_make_box(100, 100, 100), p)
    return p


def build_concentric_shell() -> Path:
    """Cu sphere R=20 inside a hollow Al shell R=20→50."""
    al_outer = _make_sphere(50.0)
    al_cavity = _make_sphere(20.0)
    al_shell = _cut(al_outer, al_cavity)
    cu_sphere = _make_sphere(20.0)
    compound = _make_compound([al_shell, cu_sphere])
    p = STEP_DIR / "concentric_shell.step"
    _write_step(compound, p)
    return p


def build_hollow_box() -> Path:
    """Box with internal cubic void (single solid, two shells)."""
    outer = _make_box(100, 100, 100)
    inner = _make_box(80, 80, 80)
    hollow = _cut(outer, inner)
    p = STEP_DIR / "hollow_box.step"
    _write_step(hollow, p)
    return p


def build_reversed_outer() -> Path:
    """Box with deliberately reversed outer-shell topology.

    We build a normal box then reverse its orientation via TopoDS.Reversed().
    """
    from OCC.Core.TopoDS import TopoDS_Shape

    box = _make_box(100, 100, 100)
    reversed_box: TopoDS_Shape = box.Reversed()  # type: ignore[assignment]
    p = STEP_DIR / "reversed_outer.step"
    _write_step(reversed_box, p)
    return p


def build_nested_pin() -> Path:
    """Smaller cylinder fully inside a larger box — accepted_nested."""
    box = _make_box(100, 100, 100)
    cyl = _translate(_make_cylinder(10, 50), 0, 0, -25)
    compound = _make_compound([box, cyl])
    p = STEP_DIR / "nested_pin.step"
    _write_step(compound, p)
    return p


def build_interference_partial_small() -> Path:
    """Two small boxes overlapping by ~0.5 mm³ — interference_warning.

    10×10×10 boxes offset by 9.995 mm along X → overlap region is
    0.005 mm × 10 mm × 10 mm = 0.5 mm³.  Below both the 1 mm³
    absolute threshold and the 0.1% relative threshold (V_smaller =
    1000 mm³, 0.1% = 1 mm³), so classifies as interference_warning.
    """
    box_a = _make_box(10, 10, 10)
    box_b = _translate(_make_box(10, 10, 10), 9.995, 0, 0)
    compound = _make_compound([box_a, box_b])
    p = STEP_DIR / "interference_partial_small.step"
    _write_step(compound, p)
    return p


def build_interference_partial_large() -> Path:
    """Two boxes overlapping by ~10 mm along X — interference_fail."""
    box_a = _make_box(100, 100, 100)
    box_b = _translate(_make_box(100, 100, 100), 90, 0, 0)
    compound = _make_compound([box_a, box_b])
    p = STEP_DIR / "interference_partial_large.step"
    _write_step(compound, p)
    return p


def build_coincident_faces() -> Path:
    """Two boxes sharing a face via BRepAlgoAPI_Splitter (topology-shared).

    A 200×100×100 box is split in half by a plane at X=0, producing two
    100×100×100 solids that share the cut face with identical topology.
    BRepMesh produces identical triangulations on both sides.
    """
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Splitter
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCC.Core.gp import gp_Dir, gp_Pln, gp_Pnt
    from OCC.Core.TopTools import TopTools_ListOfShape

    box = _make_box(200, 100, 100)
    plane = gp_Pln(gp_Pnt(0, 0, 0), gp_Dir(1, 0, 0))
    splitter_face = BRepBuilderAPI_MakeFace(plane, -60, 60, -60, 60).Face()

    splitter = BRepAlgoAPI_Splitter()
    args = TopTools_ListOfShape()
    args.Append(box)
    tools = TopTools_ListOfShape()
    tools.Append(splitter_face)
    splitter.SetArguments(args)
    splitter.SetTools(tools)
    splitter.Build()

    p = STEP_DIR / "coincident_faces.step"
    _write_step(splitter.Shape(), p)
    return p


def build_coincident_faces_mismatched() -> Path:
    """Two boxes coplanar but tessellated independently (separate TopoDS_Faces).

    Deliberately placed so they share a plane at X=50 but have separate
    face topology — BRepMesh produces different triangulations.
    """
    box_a = _make_box(100, 100, 100)
    box_b = _translate(_make_box(100, 100, 100), 100, 0, 0)
    compound = _make_compound([box_a, box_b])
    p = STEP_DIR / "coincident_faces_mismatched.step"
    _write_step(compound, p)
    return p


def build_coincident_faces_partial() -> Path:
    """Coplanar contact where one face is a sub-rectangle of the other.

    Box A: 100x100x100 centered. Box B: 50x50x100 shifted so its -X face
    sits on box A's +X face — partial coverage (~25% of A's face area).
    """
    box_a = _make_box(100, 100, 100)
    box_b = _translate(_make_box(50, 50, 100), 75, 0, 0)
    compound = _make_compound([box_a, box_b])
    p = STEP_DIR / "coincident_faces_partial.step"
    _write_step(compound, p)
    return p


# ---------------------------------------------------------------------------


def _emit_manifest(files: dict[str, Path]) -> None:
    manifest = {
        "files": {
            name: {
                "path": str(p.relative_to(ROOT).as_posix()),
                "sha256": _sha256(p),
            }
            for name, p in sorted(files.items())
        }
    }
    (STEP_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )


def main() -> int:
    STEP_DIR.mkdir(parents=True, exist_ok=True)
    builders: list[tuple[str, object]] = [
        ("aluminum_box", build_aluminum_box),
        ("concentric_shell", build_concentric_shell),
        ("hollow_box", build_hollow_box),
        ("reversed_outer", build_reversed_outer),
        ("nested_pin", build_nested_pin),
        ("interference_partial_small", build_interference_partial_small),
        ("interference_partial_large", build_interference_partial_large),
        ("coincident_faces", build_coincident_faces),
        ("coincident_faces_mismatched", build_coincident_faces_mismatched),
        ("coincident_faces_partial", build_coincident_faces_partial),
    ]
    files: dict[str, Path] = {}
    for name, fn in builders:
        print(f"  building {name}")
        p = fn()  # type: ignore[operator]
        files[name] = p
    _emit_manifest(files)
    print(f"  STEP fixtures written to {STEP_DIR.relative_to(ROOT)}/")
    for name, p in sorted(files.items()):
        print(f"    {name}: {_sha256(p)[:12]}…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
