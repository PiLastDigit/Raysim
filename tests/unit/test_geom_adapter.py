"""Phase B1.6: adapter — STL export determinism, validation gates, tied-group handoff."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("OCC.Core")

from raysim.geom.adapter import (
    build_scene_from_step,
    export_assembly_to_stl,
)
from raysim.geom.pipeline import build_assembly_from_step
from raysim.proj.schema import Material

ROOT = Path(__file__).resolve().parents[2]
STEP_DIR = ROOT / "benchmarks" / "step"


@pytest.mark.needs_occt
def test_stl_export_determinism(tmp_path: Path) -> None:
    """Two consecutive exports of the same assembly produce byte-identical STLs."""
    asm = build_assembly_from_step(STEP_DIR / "aluminum_box.step")
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    export_a = export_assembly_to_stl(asm, dir_a)
    export_b = export_assembly_to_stl(asm, dir_b)
    assert len(export_a) == len(export_b)
    for ea, eb in zip(export_a, export_b, strict=True):
        assert ea.path.read_bytes() == eb.path.read_bytes()


@pytest.mark.needs_occt
def test_stl_face_order_roundtrip(tmp_path: Path) -> None:
    """STL face order matches the index map after loading with process=False."""
    import trimesh

    asm = build_assembly_from_step(STEP_DIR / "aluminum_box.step")
    exported = export_assembly_to_stl(asm, tmp_path)
    for es in exported:
        mesh = trimesh.load(es.path, force="mesh", process=False)
        assert isinstance(mesh, trimesh.Trimesh)
        n_tris = mesh.faces.shape[0]
        assert n_tris > 0
        assert set(es.triangle_index_map.tolist()) == set(range(n_tris))


@pytest.mark.needs_occt
def test_aluminum_box_scene_roundtrip() -> None:
    """STEP→adapter→BuiltScene produces a valid scene for aluminum_box."""
    mats = [Material(group_id="solid_0000", density_g_cm3=2.70, z_eff=13.0)]
    scene, _asm = build_scene_from_step(
        STEP_DIR / "aluminum_box.step",
        materials=mats,
    )
    assert len(scene.solids) == 1
    assert scene.solids[0].density_g_cm3 == pytest.approx(2.70)
    assert scene.bbox_diag_mm > 0


@pytest.mark.needs_occt
def test_watertightness_gate_clean() -> None:
    """Watertight fixture passes without raising."""
    mats = [Material(group_id="solid_0000", density_g_cm3=2.70, z_eff=13.0)]
    _scene, asm = build_scene_from_step(
        STEP_DIR / "aluminum_box.step",
        materials=mats,
    )
    assert asm.watertightness.is_watertight()


@pytest.mark.needs_occt
def test_override_recorded_on_assembly() -> None:
    """Override flags are recorded in ValidatedAssembly.overrides_used."""
    mats = [Material(group_id="solid_0000", density_g_cm3=2.70, z_eff=13.0)]
    _, asm = build_scene_from_step(
        STEP_DIR / "aluminum_box.step",
        materials=mats,
        accept_warnings=True,
        accept_watertightness_failures=True,
    )
    assert asm.overrides_used.accept_warnings is True
    assert asm.overrides_used.accept_watertightness_failures is True
    assert asm.overrides_used.accept_interference_fail is False
