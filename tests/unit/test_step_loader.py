"""Phase B1.1 + B3.0: STEP loader — load fixtures, leaf walk order, bbox, XCAF fields."""

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


@pytest.mark.needs_occt
def test_xcaf_fields_present() -> None:
    """B3.0: LeafSolid has name/color_rgb/material_hint fields (may be None)."""
    node = load_step(STEP_DIR / "aluminum_box.step")
    leaf = next(iter_leaves(node))
    assert hasattr(leaf, "name")
    assert hasattr(leaf, "color_rgb")
    assert hasattr(leaf, "material_hint")


@pytest.mark.needs_occt
def test_assembly_node_has_name() -> None:
    """B3.0: AssemblyNode has name field."""
    node = load_step(STEP_DIR / "aluminum_box.step")
    assert hasattr(node, "name")


GOLDEN_FIXTURE = ROOT / "tests" / "fixtures" / "step_leaf_golden.yaml"

STEP_FIXTURES = [
    "aluminum_box.step",
    "concentric_shell.step",
    "nested_pin.step",
    "hollow_box.step",
]


@pytest.mark.needs_occt
def test_dfs_order_regression() -> None:
    """B3.0 regression guard: leaf tuples must match golden data.

    On the first run with OCCT, generates the golden fixture YAML.
    Subsequent runs assert exact match — a walk-order change would break
    existing project files whose assignments key on solid_id.
    """
    import yaml

    current: dict[str, list[dict[str, object]]] = {}
    for step_name in STEP_FIXTURES:
        step_file = STEP_DIR / step_name
        if not step_file.exists():
            pytest.skip(f"Missing {step_file}")
        node = load_step(step_file)
        leaves = list(iter_leaves(node))
        current[step_name] = [
            {
                "solid_id": leaf.solid_id,
                "path_key": leaf.path_key,
                "bbox_min_mm": list(leaf.bbox_min_mm),
                "bbox_max_mm": list(leaf.bbox_max_mm),
            }
            for leaf in leaves
        ]

    if not GOLDEN_FIXTURE.exists():
        GOLDEN_FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN_FIXTURE.write_text(
            yaml.dump(current, default_flow_style=False), encoding="utf-8",
        )
        pytest.skip("Generated golden fixture; re-run to verify")

    golden = yaml.safe_load(GOLDEN_FIXTURE.read_text(encoding="utf-8"))
    for step_name in STEP_FIXTURES:
        assert step_name in golden, f"Golden fixture missing {step_name}"
        assert len(current[step_name]) == len(golden[step_name]), (
            f"{step_name}: leaf count changed"
        )
        for i, (cur, gold) in enumerate(
            zip(current[step_name], golden[step_name], strict=True),
        ):
            assert cur["solid_id"] == gold["solid_id"], (
                f"{step_name}[{i}]: solid_id {cur['solid_id']} != {gold['solid_id']}"
            )
            assert cur["path_key"] == gold["path_key"], (
                f"{step_name}[{i}]: path_key {cur['path_key']} != {gold['path_key']}"
            )
            for j in range(3):
                assert cur["bbox_min_mm"][j] == pytest.approx(
                    gold["bbox_min_mm"][j], abs=1e-3,
                ), f"{step_name}[{i}]: bbox_min_mm[{j}] mismatch"
                assert cur["bbox_max_mm"][j] == pytest.approx(
                    gold["bbox_max_mm"][j], abs=1e-3,
                ), f"{step_name}[{i}]: bbox_max_mm[{j}] mismatch"
