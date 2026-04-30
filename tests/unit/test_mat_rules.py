"""Tests for raysim.mat.rules — Phase B2.3."""

from __future__ import annotations

from pathlib import Path

from raysim.mat.rules import NamingRule, SolidRef, apply_rules, load_rules


def test_load_default_rules() -> None:
    rules = load_rules()
    assert len(rules) > 0
    assert all(isinstance(r, NamingRule) for r in rules)


def test_solid_ref_default_display_name() -> None:
    ref = SolidRef(solid_id="s1", path_key="0/1")
    assert ref.display_name == "s1"


def test_solid_ref_explicit_display_name() -> None:
    ref = SolidRef(solid_id="s1", path_key="0/1", display_name="Panel")
    assert ref.display_name == "Panel"


def test_match_aluminum() -> None:
    rules = load_rules()
    solids = [SolidRef(solid_id="AL_PANEL_TOP", path_key="0/0")]
    results = apply_rules(rules, solids)
    assert len(results) == 1
    assert results[0].matched_group_id == "aluminum_6061"
    assert not results[0].is_ambiguous


def test_match_copper() -> None:
    rules = load_rules()
    solids = [SolidRef(solid_id="CU_TRACE", path_key="0/1")]
    results = apply_rules(rules, solids)
    assert results[0].matched_group_id == "copper"


def test_match_fr4() -> None:
    rules = load_rules()
    solids = [SolidRef(solid_id="PCB_FR4_LAYER", path_key="0/2")]
    results = apply_rules(rules, solids)
    assert results[0].matched_group_id == "fr4"


def test_match_kapton() -> None:
    rules = load_rules()
    solids = [SolidRef(solid_id="KAPTON_WRAP", path_key="0/3")]
    results = apply_rules(rules, solids)
    assert results[0].matched_group_id == "kapton"


def test_match_battery() -> None:
    rules = load_rules()
    solids = [SolidRef(solid_id="BATT_CELL_01", path_key="0/4")]
    results = apply_rules(rules, solids)
    assert results[0].matched_group_id == "battery"


def test_no_match() -> None:
    rules = load_rules()
    solids = [SolidRef(solid_id="UNKNOWN_PART_XYZ", path_key="0/99")]
    results = apply_rules(rules, solids)
    assert results[0].matched_group_id is None
    assert not results[0].is_ambiguous


def test_path_key_match() -> None:
    rules = [NamingRule(pattern="(?i)copper", group_id="copper", priority=10)]
    solids = [SolidRef(solid_id="solid_0001", path_key="copper_housing/0")]
    results = apply_rules(rules, solids)
    assert results[0].matched_group_id == "copper"


def test_display_name_match() -> None:
    rules = [NamingRule(pattern="(?i)aluminum", group_id="aluminum_6061", priority=10)]
    solids = [SolidRef(solid_id="s1", path_key="0", display_name="Aluminum Panel")]
    results = apply_rules(rules, solids)
    assert results[0].matched_group_id == "aluminum_6061"


def test_priority_ordering() -> None:
    rules = [
        NamingRule(pattern=".*", group_id="low_prio", priority=1),
        NamingRule(pattern=".*", group_id="high_prio", priority=20),
    ]
    solids = [SolidRef(solid_id="anything", path_key="0")]
    results = apply_rules(rules, solids)
    assert results[0].matched_group_id == "high_prio"


def test_ambiguous_same_priority_different_ids() -> None:
    rules = [
        NamingRule(pattern=".*", group_id="mat_a", priority=10),
        NamingRule(pattern=".*", group_id="mat_b", priority=10),
    ]
    solids = [SolidRef(solid_id="x", path_key="0")]
    results = apply_rules(rules, solids)
    assert results[0].is_ambiguous
    assert results[0].matched_group_id is None


def test_same_priority_same_id_not_ambiguous() -> None:
    rules = [
        NamingRule(pattern="AL", group_id="aluminum_6061", priority=10, source="rule_a"),
        NamingRule(pattern="ALUM", group_id="aluminum_6061", priority=10, source="rule_b"),
    ]
    solids = [SolidRef(solid_id="ALUMINUM_PANEL", path_key="0")]
    results = apply_rules(rules, solids)
    assert not results[0].is_ambiguous
    assert results[0].matched_group_id == "aluminum_6061"


def test_load_custom_rules(tmp_path: Path) -> None:
    p = tmp_path / "rules.yaml"
    p.write_text("rules:\n  - pattern: test\n    group_id: test_mat\n    priority: 5\n")
    rules = load_rules(p)
    assert len(rules) == 1
    assert rules[0].group_id == "test_mat"
    assert rules[0].priority == 5
