"""Tests for raysim.mat.step_tags — Phase B2.2 + B3.0 simplification.

Pure-Python tests (similarity, match_tags_to_library) run without OCCT.
After B3.0, extract_step_tags reads from LeafSolid fields — no OCCT needed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from raysim.mat.library import load_library
from raysim.mat.step_tags import StepMaterialTag, _similarity, match_tags_to_library


def test_similarity_exact_match() -> None:
    assert _similarity("copper", "copper", "Cu (OFHC)") == 1.0


def test_similarity_substring() -> None:
    assert _similarity("al", "aluminum_6061", "Al 6061") >= 0.7


def test_similarity_no_match() -> None:
    assert _similarity("xyz123", "copper", "Cu (OFHC)") < 0.5


def test_match_tags_to_library_exact() -> None:
    lib = load_library()
    tags = [
        StepMaterialTag(solid_id="s0", material_name="copper", color_rgb=None),
        StepMaterialTag(solid_id="s1", material_name=None, color_rgb=None),
    ]
    matches = match_tags_to_library(tags, lib)
    assert len(matches) == 2
    assert matches[0].matched_group_id == "copper"
    assert matches[0].confidence == 1.0
    assert matches[1].matched_group_id is None
    assert matches[1].confidence == 0.0


def test_match_tags_below_threshold() -> None:
    lib = load_library()
    tags = [StepMaterialTag(solid_id="s0", material_name="zzz_unknown", color_rgb=None)]
    matches = match_tags_to_library(tags, lib, threshold=0.9)
    assert matches[0].matched_group_id is None


def test_empty_string_tag_treated_as_unmatched() -> None:
    lib = load_library()
    tags = [
        StepMaterialTag(solid_id="s0", material_name="", color_rgb=None),
        StepMaterialTag(solid_id="s1", material_name="   ", color_rgb=None),
    ]
    matches = match_tags_to_library(tags, lib)
    assert matches[0].matched_group_id is None
    assert matches[1].matched_group_id is None


def test_extract_step_tags_from_leaf_solids() -> None:
    """B3.0: extract_step_tags reads from LeafSolid fields (no OCCT needed)."""
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class FakeLeaf:
        solid_id: str
        path_key: str
        shape: object
        bbox_min_mm: tuple[float, float, float]
        bbox_max_mm: tuple[float, float, float]
        name: str | None = None
        color_rgb: tuple[float, float, float] | None = None
        material_hint: str | None = None

    from raysim.mat.step_tags import extract_step_tags

    leaves = [
        FakeLeaf(
            solid_id="solid_0000", path_key="0", shape=None,
            bbox_min_mm=(0.0, 0.0, 0.0), bbox_max_mm=(1.0, 1.0, 1.0),
            name="Housing", color_rgb=(0.5, 0.5, 0.5), material_hint="aluminum",
        ),
        FakeLeaf(
            solid_id="solid_0001", path_key="1", shape=None,
            bbox_min_mm=(0.0, 0.0, 0.0), bbox_max_mm=(2.0, 2.0, 2.0),
            name="Shield", color_rgb=None, material_hint=None,
        ),
    ]
    tags = extract_step_tags(leaves)  # type: ignore[arg-type]
    assert len(tags) == 2
    assert tags[0].solid_id == "solid_0000"
    assert tags[0].material_name == "aluminum"
    assert tags[0].color_rgb == (0.5, 0.5, 0.5)
    assert tags[1].material_name is None
    assert tags[1].color_rgb is None


@pytest.mark.needs_occt
def test_extract_step_tags_on_benchmark_step() -> None:
    """Integration test: load a benchmark STEP and verify tags via LeafSolid."""
    try:
        import OCC.Core  # noqa: F401
    except ImportError:
        pytest.skip("pythonocc-core not installed")

    step_dir = Path("benchmarks/step")
    if not step_dir.exists():
        pytest.skip("benchmark STEP fixtures not available")

    from raysim.geom.step_loader import iter_leaves, load_step
    from raysim.mat.step_tags import extract_step_tags

    step_file = step_dir / "aluminum_box.step"
    if not step_file.exists():
        pytest.skip(f"Missing {step_file}")

    tree = load_step(step_file)
    leaves = list(iter_leaves(tree))
    tags = extract_step_tags(leaves)
    assert isinstance(tags, list)
    if tags:
        assert len(tags) == len(leaves)
