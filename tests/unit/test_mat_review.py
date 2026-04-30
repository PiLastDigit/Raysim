"""Tests for raysim.mat.review — Phase B2.4."""

from __future__ import annotations

import pytest

from raysim.mat.library import MaterialLibrary, _build_library
from raysim.mat.review import (
    build_review,
    format_review_summary,
    review_to_assignments,
)
from raysim.mat.rules import RuleMatch, SolidRef
from raysim.mat.step_tags import TagMatch
from raysim.proj.schema import Material, MaterialAssignment


@pytest.fixture()
def small_lib() -> MaterialLibrary:
    return _build_library([
        Material(group_id="aluminum", density_g_cm3=2.70),
        Material(group_id="copper", density_g_cm3=8.96),
    ])


def _solids(*names: str) -> list[SolidRef]:
    return [SolidRef(solid_id=n, path_key=n) for n in names]


def test_manual_wins(small_lib: MaterialLibrary) -> None:
    review = build_review(
        _solids("s0"),
        manual_assignments=[MaterialAssignment(solid_id="s0", material_group_id="copper")],
        rule_matches=[RuleMatch(solid_id="s0", matched_group_id="aluminum", is_ambiguous=False, candidates=())],
        library=small_lib,
    )
    assert review.statuses[0].source == "manual"
    assert review.statuses[0].material_group_id == "copper"


def test_step_tag_wins_over_rule(small_lib: MaterialLibrary) -> None:
    review = build_review(
        _solids("s0"),
        tag_matches=[TagMatch(solid_id="s0", matched_group_id="copper", confidence=0.9, raw_tag="Cu")],
        rule_matches=[RuleMatch(solid_id="s0", matched_group_id="aluminum", is_ambiguous=False, candidates=())],
        library=small_lib,
    )
    assert review.statuses[0].source == "step_tag"
    assert review.statuses[0].material_group_id == "copper"


def test_rule_fallback(small_lib: MaterialLibrary) -> None:
    review = build_review(
        _solids("s0"),
        rule_matches=[RuleMatch(solid_id="s0", matched_group_id="aluminum", is_ambiguous=False, candidates=())],
        library=small_lib,
    )
    assert review.statuses[0].source == "naming_rule"
    assert review.statuses[0].material_group_id == "aluminum"


def test_unassigned(small_lib: MaterialLibrary) -> None:
    review = build_review(_solids("s0"), library=small_lib)
    assert review.statuses[0].source == "unassigned"
    assert review.n_unassigned == 1


def test_ambiguous_rule(small_lib: MaterialLibrary) -> None:
    from raysim.mat.rules import NamingRule

    review = build_review(
        _solids("s0"),
        rule_matches=[RuleMatch(
            solid_id="s0", matched_group_id=None, is_ambiguous=True,
            candidates=(
                NamingRule(pattern="a", group_id="aluminum", priority=10),
                NamingRule(pattern="b", group_id="copper", priority=10),
            ),
        )],
        library=small_lib,
    )
    assert review.statuses[0].is_ambiguous
    assert review.n_ambiguous == 1


def test_counters(small_lib: MaterialLibrary) -> None:
    review = build_review(
        _solids("s0", "s1", "s2"),
        manual_assignments=[MaterialAssignment(solid_id="s0", material_group_id="aluminum")],
        rule_matches=[RuleMatch(solid_id="s1", matched_group_id="copper", is_ambiguous=False, candidates=())],
        library=small_lib,
    )
    assert review.n_auto_matched == 2
    assert review.n_unassigned == 1


def test_review_to_assignments_success(small_lib: MaterialLibrary) -> None:
    review = build_review(
        _solids("s0", "s1"),
        manual_assignments=[
            MaterialAssignment(solid_id="s0", material_group_id="aluminum"),
            MaterialAssignment(solid_id="s1", material_group_id="copper"),
        ],
        library=small_lib,
    )
    assignments = review_to_assignments(review)
    assert len(assignments) == 2
    assert assignments[0].solid_id == "s0"


def test_invalid_manual_stays_unresolved(small_lib: MaterialLibrary) -> None:
    review = build_review(
        _solids("s0"),
        manual_assignments=[MaterialAssignment(solid_id="s0", material_group_id="nonexistent_mat")],
        rule_matches=[RuleMatch(solid_id="s0", matched_group_id="aluminum", is_ambiguous=False, candidates=())],
        library=small_lib,
    )
    assert review.statuses[0].source == "manual"
    assert review.statuses[0].material_group_id is None
    assert review.n_unassigned == 1


def test_review_to_assignments_unresolved_raises(small_lib: MaterialLibrary) -> None:
    review = build_review(_solids("s0"), library=small_lib)
    with pytest.raises(ValueError, match="unresolved"):
        review_to_assignments(review)


def test_format_review_summary(small_lib: MaterialLibrary) -> None:
    review = build_review(
        _solids("s0", "s1"),
        manual_assignments=[MaterialAssignment(solid_id="s0", material_group_id="aluminum")],
        library=small_lib,
    )
    summary = format_review_summary(review)
    assert "2 solids" in summary
    assert "auto-matched: 1" in summary
    assert "unassigned:   1" in summary
    assert "UNASSIGNED" in summary


def test_format_review_summary_unresolved_manual(small_lib: MaterialLibrary) -> None:
    review = build_review(
        _solids("s0"),
        manual_assignments=[MaterialAssignment(solid_id="s0", material_group_id="nonexistent_mat")],
        library=small_lib,
    )
    summary = format_review_summary(review)
    assert "UNRESOLVED manual" in summary
