"""Tests for raysim.mat.step_tags — Phase B2.2.

Pure-Python tests (similarity, match_tags_to_library) run without OCCT.
Integration tests for extract_step_tags require pythonocc-core.
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


@pytest.mark.needs_occt
def test_extract_step_tags_on_benchmark_step() -> None:
    """Integration test: load a benchmark STEP with XCAF and verify tag count."""
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
    tags = extract_step_tags(step_file, leaves)
    assert isinstance(tags, list)
    if tags:
        assert len(tags) == len(leaves)
