"""Phase B1.1: STEP loader — load fixtures, leaf walk order, bbox correctness."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("OCC.Core")

from raysim.geom.step_loader import iter_leaves, load_step

ROOT = Path(__file__).resolve().parents[2]
STEP_DIR = ROOT / "benchmarks" / "step"


@pytest.mark.needs_occt
def test_aluminum_box_loads() -> None:
    node = load_step(STEP_DIR / "aluminum_box.step")
    leaves = list(iter_leaves(node))
    assert len(leaves) == 1
    leaf = leaves[0]
    assert leaf.solid_id == "solid_0000"
    assert leaf.bbox_min_mm[0] < leaf.bbox_max_mm[0]


@pytest.mark.needs_occt
def test_concentric_shell_two_solids() -> None:
    node = load_step(STEP_DIR / "concentric_shell.step")
    leaves = list(iter_leaves(node))
    assert len(leaves) == 2
    ids = {leaf.solid_id for leaf in leaves}
    assert ids == {"solid_0000", "solid_0001"}


@pytest.mark.needs_occt
def test_leaf_walk_order_is_stable() -> None:
    node1 = load_step(STEP_DIR / "concentric_shell.step")
    node2 = load_step(STEP_DIR / "concentric_shell.step")
    ids1 = [leaf.solid_id for leaf in iter_leaves(node1)]
    ids2 = [leaf.solid_id for leaf in iter_leaves(node2)]
    assert ids1 == ids2


@pytest.mark.needs_occt
def test_bbox_correctness_aluminum_box() -> None:
    node = load_step(STEP_DIR / "aluminum_box.step")
    leaf = next(iter_leaves(node))
    for i in range(3):
        extent = leaf.bbox_max_mm[i] - leaf.bbox_min_mm[i]
        assert extent == pytest.approx(100.0, abs=1.0)


@pytest.mark.needs_occt
def test_nested_pin_two_solids() -> None:
    node = load_step(STEP_DIR / "nested_pin.step")
    leaves = list(iter_leaves(node))
    assert len(leaves) == 2


@pytest.mark.needs_occt
def test_missing_file_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_step("/nonexistent/path.step")


@pytest.mark.needs_occt
def test_hollow_box_single_solid() -> None:
    node = load_step(STEP_DIR / "hollow_box.step")
    leaves = list(iter_leaves(node))
    assert len(leaves) == 1
