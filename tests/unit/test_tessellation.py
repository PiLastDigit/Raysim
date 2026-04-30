"""Phase B1.2: tessellation — triangle counts, per-shell grouping, transforms."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("OCC.Core")

from raysim.geom.step_loader import iter_leaves, load_step
from raysim.geom.tessellation import flatten_index, tessellate

ROOT = Path(__file__).resolve().parents[2]
STEP_DIR = ROOT / "benchmarks" / "step"


@pytest.mark.needs_occt
def test_aluminum_box_triangles() -> None:
    leaf = next(iter_leaves(load_step(STEP_DIR / "aluminum_box.step")))
    ts = tessellate(leaf)
    total_tris = sum(s.faces.shape[0] for s in ts.shells)
    assert total_tris >= 12  # at least 2 tris per face × 6 faces


@pytest.mark.needs_occt
def test_per_shell_grouping_hollow_box() -> None:
    """Hollow box has two shells: outer and cavity."""
    leaf = next(iter_leaves(load_step(STEP_DIR / "hollow_box.step")))
    ts = tessellate(leaf)
    assert len(ts.shells) == 2


@pytest.mark.needs_occt
def test_normals_are_unit_length() -> None:
    leaf = next(iter_leaves(load_step(STEP_DIR / "aluminum_box.step")))
    ts = tessellate(leaf)
    for shell in ts.shells:
        norms = np.linalg.norm(shell.triangle_normals, axis=1)
        np.testing.assert_allclose(norms, 1.0, atol=1e-12)


@pytest.mark.needs_occt
def test_flatten_index_consistency() -> None:
    leaf = next(iter_leaves(load_step(STEP_DIR / "hollow_box.step")))
    ts = tessellate(leaf)
    idx = 0
    for shell in ts.shells:
        for prim in range(shell.faces.shape[0]):
            assert flatten_index(ts, shell.shell_index, prim) == idx
            idx += 1


@pytest.mark.needs_occt
def test_concentric_shell_tessellates() -> None:
    leaves = list(iter_leaves(load_step(STEP_DIR / "concentric_shell.step")))
    for leaf in leaves:
        ts = tessellate(leaf)
        total_tris = sum(s.faces.shape[0] for s in ts.shells)
        assert total_tris > 0


@pytest.mark.needs_occt
def test_vertices_are_float64() -> None:
    leaf = next(iter_leaves(load_step(STEP_DIR / "aluminum_box.step")))
    ts = tessellate(leaf)
    for shell in ts.shells:
        assert shell.vertices.dtype == np.float64
        assert shell.faces.dtype == np.int64
