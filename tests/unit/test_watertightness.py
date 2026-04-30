"""Phase B1.4: watertightness — clean shells pass, broken shells flagged."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("OCC.Core")

from raysim.geom.healing import HealedShell, HealedSolid, heal_assembly
from raysim.geom.step_loader import iter_leaves, load_step
from raysim.geom.tessellation import tessellate
from raysim.geom.watertightness import validate_watertightness

ROOT = Path(__file__).resolve().parents[2]
STEP_DIR = ROOT / "benchmarks" / "step"


def _heal_all(step_file: str) -> list:
    node = load_step(STEP_DIR / step_file)
    solids = [tessellate(leaf) for leaf in iter_leaves(node)]
    return list(heal_assembly(solids))


@pytest.mark.needs_occt
def test_aluminum_box_is_watertight() -> None:
    healed = _heal_all("aluminum_box.step")
    report = validate_watertightness(healed)
    assert report.is_watertight()
    assert len(report.failed_shells()) == 0


@pytest.mark.needs_occt
def test_hollow_box_is_watertight() -> None:
    healed = _heal_all("hollow_box.step")
    report = validate_watertightness(healed)
    assert report.is_watertight()


@pytest.mark.needs_occt
def test_concentric_shell_is_watertight() -> None:
    healed = _heal_all("concentric_shell.step")
    report = validate_watertightness(healed)
    assert report.is_watertight()


@pytest.mark.needs_occt
def test_broken_shell_detected() -> None:
    """Synthetically break a shell by removing a triangle, then verify detection."""
    healed = _heal_all("aluminum_box.step")
    solid = healed[0]
    shell = solid.shells[0]

    broken_shell = HealedShell(
        shell_index=shell.shell_index,
        vertices=shell.vertices,
        faces=shell.faces[:-1],
        triangle_normals=shell.triangle_normals[:-1],
        role=shell.role,
        was_flipped=shell.was_flipped,
    )
    broken_solid = HealedSolid(
        solid_id=solid.solid_id,
        shells=(broken_shell,),
        bbox_min_mm=solid.bbox_min_mm,
        bbox_max_mm=solid.bbox_max_mm,
    )
    report = validate_watertightness([broken_solid])
    assert not report.is_watertight()
    failed = report.failed_shells()
    assert len(failed) >= 1
    assert failed[0][0] == solid.solid_id
