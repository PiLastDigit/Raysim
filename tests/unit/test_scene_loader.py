"""Phase A.3: scene loader + Embree BVH + tied-group detection."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("embreex")

from raysim.proj.schema import Material, MaterialAssignment
from raysim.ray.scene import load_scene_from_directory

ROOT = Path(__file__).resolve().parents[2]
GEOM = ROOT / "benchmarks" / "geometries"

ALL_MATERIALS = [
    Material(group_id="aluminum", density_g_cm3=2.70, z_eff=13.0, display_name="Al 6061"),
    Material(group_id="copper", density_g_cm3=8.96, z_eff=29.0, display_name="Cu"),
    Material(group_id="fr4", density_g_cm3=1.85, z_eff=10.0, display_name="FR4"),
    Material(group_id="gaas", density_g_cm3=5.32, z_eff=32.0, display_name="GaAs"),
]


def test_aluminum_box_loads() -> None:
    scene = load_scene_from_directory(GEOM / "aluminum_box", ALL_MATERIALS)
    assert len(scene.solids) == 1
    s = scene.solids[0]
    assert s.solid_id == "aluminum"
    assert s.density_g_cm3 == pytest.approx(2.70)
    assert s.n_triangles == 12
    assert scene.bbox_diag_mm == pytest.approx(np.linalg.norm([100.0] * 3), rel=1e-3)


def test_concentric_shell_tied_group_detected() -> None:
    """The Al cavity shell at R=20 and the Cu outer shell at R=20 share every
    vertex by construction (both are uv_sphere(20, count=[64,64])). The tied-
    group detector must pair them — this is the workload that lets Phase A.4
    handle the tie batch correctly."""
    scene = load_scene_from_directory(GEOM / "concentric_shell", ALL_MATERIALS)
    assert len(scene.solids) == 2
    # uv_sphere(64,64) → 4032 triangles per shell. Cu has 1 shell; Al has 2
    # (outer R=50 + inner R=20). The R=20 ones are the only coincident pair.
    n_groups = len(scene.tied_group_members)
    # Every triangle in the Cu mesh has a partner in the Al inner shell.
    cu_geom = next(s.geom_id for s in scene.solids if s.solid_id == "copper")
    al_geom = next(s.geom_id for s in scene.solids if s.solid_id == "aluminum")
    cu_tied = scene.tied_group_id_per_geom[cu_geom]
    al_tied = scene.tied_group_id_per_geom[al_geom]
    assert int(np.sum(cu_tied >= 0)) == cu_tied.size  # every Cu tri tied
    # Al has outer + inner shell; only the inner ones are tied.
    n_al_inner = int(np.sum(al_tied >= 0))
    assert n_al_inner == cu_tied.size
    # Each tied group has exactly two members (one Al-inner + one Cu-outer).
    assert all(len(v) == 2 for v in scene.tied_group_members.values())
    assert n_groups == cu_tied.size


def test_solid_sphere_no_ties() -> None:
    """Single-solid scenes have no coincident faces."""
    scene = load_scene_from_directory(GEOM / "solid_sphere", ALL_MATERIALS)
    assert len(scene.tied_group_members) == 0
    assert np.all(scene.tied_group_id_per_geom[0] == -1)


def test_unknown_material_raises(tmp_path: Path) -> None:
    # An STL whose stem doesn't match any library entry should fail loud.
    src = GEOM / "aluminum_box" / "aluminum.stl"
    bad_dir = tmp_path / "scene"
    bad_dir.mkdir()
    (bad_dir / "unobtanium.stl").write_bytes(src.read_bytes())
    with pytest.raises(KeyError, match="not in library"):
        load_scene_from_directory(bad_dir, ALL_MATERIALS)


def test_assignment_overrides_solid_id() -> None:
    """When an assignment is given, it overrides the solid_id-as-material fallback."""
    scene = load_scene_from_directory(
        GEOM / "aluminum_box",
        ALL_MATERIALS,
        assignments=[MaterialAssignment(solid_id="aluminum", material_group_id="copper")],
    )
    assert scene.solids[0].material_group_id == "copper"
    assert scene.density_per_geom[0] == pytest.approx(8.96)
