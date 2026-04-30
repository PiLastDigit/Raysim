"""Phase B1 acceptance — full STEP→BuiltScene round-trip on canonical fixtures.

Verifies that the STEP geometry pipeline produces a ``BuiltScene`` that the
Stage A engine consumes unchanged, and that ∑ρL on principal-axis rays
matches the existing analytic targets within tessellation tolerance.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("OCC.Core")
pytest.importorskip("embreex")

from raysim.geom.adapter import build_scene_from_step
from raysim.proj.schema import Material
from raysim.ray.tracer import trace_rays

ROOT = Path(__file__).resolve().parents[2]
STEP_DIR = ROOT / "benchmarks" / "step"


MATS_CONCENTRIC = [
    Material(group_id="solid_0000", density_g_cm3=2.70, z_eff=13.0, display_name="Al"),
    Material(group_id="solid_0001", density_g_cm3=8.96, z_eff=29.0, display_name="Cu"),
]


@pytest.mark.needs_occt
@pytest.mark.slow
def test_aluminum_box_sigma_rho_l() -> None:
    """STEP→engine ∑ρL on the aluminum box matches analytic target."""
    mats = [Material(group_id="solid_0000", density_g_cm3=2.70, z_eff=13.0)]
    scene, _asm = build_scene_from_step(STEP_DIR / "aluminum_box.step", materials=mats)

    origins = np.array([[0.0, 0.0, 200.0]])
    dirs = np.array([[0.0, 0.0, -1.0]])
    res = trace_rays(scene, origins, dirs)

    expected = 27.0  # 2.70 g/cm³ × 10 cm
    rel = abs(res.sigma_rho_l_g_cm2[0] - expected) / expected
    assert rel < 0.005, f"∑ρL off by {rel:.3%} (expected ≤0.5%)"


@pytest.mark.needs_occt
@pytest.mark.slow
def test_concentric_shell_sigma_rho_l() -> None:
    """STEP→engine ∑ρL on concentric shell matches analytic target."""
    scene, _asm = build_scene_from_step(
        STEP_DIR / "concentric_shell.step",
        materials=MATS_CONCENTRIC,
    )

    origins = np.array([[0.0, 0.0, 200.0]])
    dirs = np.array([[0.0, 0.0, -1.0]])
    res = trace_rays(scene, origins, dirs)

    expected = 52.04  # 60 mm Al + 40 mm Cu
    rel = abs(res.sigma_rho_l_g_cm2[0] - expected) / expected
    assert rel < 0.005, f"∑ρL off by {rel:.3%} (expected ≤0.5%)"


@pytest.mark.needs_occt
@pytest.mark.slow
def test_pipeline_watertightness_passes() -> None:
    """All canonical STEP fixtures pass watertightness."""
    for step_file in ["aluminum_box.step", "hollow_box.step"]:
        mats = [Material(group_id="solid_0000", density_g_cm3=2.70, z_eff=13.0)]
        _, asm = build_scene_from_step(STEP_DIR / step_file, materials=mats)
        assert asm.watertightness.is_watertight(), f"{step_file} not watertight"
