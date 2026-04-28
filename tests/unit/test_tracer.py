"""Phase A.4: iterative closest-hit traversal with stack accumulator."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("embreex")

from raysim.proj.schema import Material
from raysim.ray import load_scene_from_directory, trace_rays

ROOT = Path(__file__).resolve().parents[2]
GEOM = ROOT / "benchmarks" / "geometries"

MATS = [
    Material(group_id="aluminum", density_g_cm3=2.70),
    Material(group_id="copper", density_g_cm3=8.96),
]


def test_aluminum_box_principal_axis() -> None:
    """Single-material box, ∑ρL = ρ × chord. No ties, no nesting."""
    scene = load_scene_from_directory(GEOM / "aluminum_box", MATS)
    origins = np.array([[0.0, 0.0, 200.0]])
    dirs = np.array([[0.0, 0.0, -1.0]])
    res = trace_rays(scene, origins, dirs)
    assert res.sigma_rho_l_g_cm2[0] == pytest.approx(27.0, rel=1e-5)
    assert res.n_hits[0] == 2
    assert not res.stack_leak[0]
    assert res.mismatch_counts[0] == 0


def test_aluminum_box_off_axis_diagonal() -> None:
    """Diagonal ray through the cube corner-to-corner: chord = 100*sqrt(3) mm."""
    scene = load_scene_from_directory(GEOM / "aluminum_box", MATS)
    # Ray along (1,1,1) normalized, going toward origin from far away.
    d = np.array([-1.0, -1.0, -1.0]) / np.sqrt(3.0)
    o = -d * 500.0  # far enough to be outside
    res = trace_rays(scene, o[None, :], d[None, :])
    expected = 100.0 * np.sqrt(3.0) * 0.1 * 2.70
    assert res.sigma_rho_l_g_cm2[0] == pytest.approx(expected, rel=1e-5)
    assert not res.stack_leak[0]


def test_concentric_shell_principal_axis() -> None:
    """Tied-batch correctness: Al cavity face + Cu outer face share vertices.
    Without tie handling, the eps advance silently skips one of them and ∑ρL
    is wrong by a factor of ρ_Cu × 40 mm — exactly the regression this fixture
    guards."""
    scene = load_scene_from_directory(GEOM / "concentric_shell", MATS)
    origins = np.array([[0.0, 0.0, 200.0]])
    dirs = np.array([[0.0, 0.0, -1.0]])
    res = trace_rays(scene, origins, dirs)
    # Analytic: 60 mm Al (R=50→20 + R=-20→-50) + 40 mm Cu (R=20→-20).
    # ∑ρL = 6.0×2.70 + 4.0×8.96 = 16.2 + 35.84 = 52.04 g/cm².
    assert res.sigma_rho_l_g_cm2[0] == pytest.approx(52.04, rel=1e-5)
    assert res.n_hits[0] == 4
    assert not res.stack_leak[0]
    assert res.mismatch_counts[0] == 0


def test_miss_returns_zero_no_leak() -> None:
    """Ray entirely outside the scene: ∑ρL = 0, no stack leak, no hits."""
    scene = load_scene_from_directory(GEOM / "aluminum_box", MATS)
    origins = np.array([[1000.0, 1000.0, 1000.0]])
    dirs = np.array([[1.0, 0.0, 0.0]])
    res = trace_rays(scene, origins, dirs)
    assert res.sigma_rho_l_g_cm2[0] == 0.0
    assert res.n_hits[0] == 0
    assert not res.stack_leak[0]


def test_max_hits_guard() -> None:
    """A pathological max_hits=1 cap forces the ray-fatal flag to be set."""
    scene = load_scene_from_directory(GEOM / "concentric_shell", MATS)
    origins = np.array([[0.0, 0.0, 200.0]])
    dirs = np.array([[0.0, 0.0, -1.0]])
    res = trace_rays(scene, origins, dirs, max_hits=1)
    assert bool(res.max_hit_exceeded[0])


def test_tangent_ray_grazes_dont_double_count() -> None:
    """A ray skimming just above a face (no surface intersection) must produce
    no hits and ∑ρL = 0. Tests the clean-miss path adjacent to a tangent geometry —
    Embree should report no hit, the stack stays empty, no spurious accumulation.
    """
    scene = load_scene_from_directory(GEOM / "aluminum_box", MATS)
    # 1e-3 mm above the +Z face along +X — clean miss, not a grazing hit.
    origins = np.array([[-200.0, 0.0, 50.0 + 1e-3]])
    dirs = np.array([[1.0, 0.0, 0.0]])
    res = trace_rays(scene, origins, dirs)
    assert res.sigma_rho_l_g_cm2[0] == 0.0
    assert not res.stack_leak[0]
    assert res.n_hits[0] == 0


def test_batch_of_many_rays() -> None:
    """Trace a batch — random directions out of the box's center should all
    accumulate ∑ρL > 0 (every direction crosses the cube)."""
    scene = load_scene_from_directory(GEOM / "aluminum_box", MATS)
    rng = np.random.default_rng(0)
    n = 50
    # Start far enough outside that every random direction enters the cube.
    origins = np.zeros((n, 3))
    origins[:, 2] = 300.0
    # Aim each ray at a random point inside the cube → guaranteed entry.
    targets = rng.uniform(-40.0, 40.0, size=(n, 3))
    dirs = targets - origins
    dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
    res = trace_rays(scene, origins, dirs)
    assert np.all(res.sigma_rho_l_g_cm2 > 0)
    assert not np.any(res.stack_leak)
    assert not np.any(res.max_hit_exceeded)
