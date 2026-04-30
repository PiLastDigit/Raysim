"""Tests for raysim.mat.library — Phase B2.1."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from raysim.mat.library import _build_library, load_library
from raysim.proj.schema import Material


def test_load_default_library() -> None:
    lib = load_library()
    assert len(lib) == 14
    assert "aluminum_6061" in lib
    assert "copper" in lib
    assert "harness" in lib


def test_default_library_densities_positive() -> None:
    lib = load_library()
    for m in lib.materials:
        assert m.density_g_cm3 > 0, f"{m.group_id} density must be positive"


def test_default_library_all_have_provenance() -> None:
    lib = load_library()
    for m in lib.materials:
        assert m.provenance, f"{m.group_id} missing provenance"


def test_lookup_by_group_id() -> None:
    lib = load_library()
    al = lib["aluminum_6061"]
    assert al.density_g_cm3 == pytest.approx(2.70)
    assert al.z_eff == pytest.approx(13.0)


def test_contains() -> None:
    lib = load_library()
    assert "copper" in lib
    assert "nonexistent" not in lib


def test_duplicate_group_id_raises() -> None:
    m1 = Material(group_id="dup", density_g_cm3=1.0)
    m2 = Material(group_id="dup", density_g_cm3=2.0)
    with pytest.raises(ValueError, match="Duplicate group_id"):
        _build_library([m1, m2])


def test_merge_adds_entries() -> None:
    lib = load_library()
    extra = _build_library([Material(group_id="custom_x", density_g_cm3=5.0)])
    merged = lib.merge(extra)
    assert "custom_x" in merged
    assert len(merged) == len(lib) + 1


def test_merge_overrides() -> None:
    lib = load_library()
    override = _build_library([Material(group_id="copper", density_g_cm3=9.99)])
    merged = lib.merge(override)
    assert merged["copper"].density_g_cm3 == pytest.approx(9.99)
    assert len(merged) == len(lib)


def test_load_custom_yaml(tmp_path: Path) -> None:
    yaml_content = dedent("""\
        materials:
          - group_id: test_mat
            density_g_cm3: 3.14
            display_name: Test Material
    """)
    p = tmp_path / "custom.yaml"
    p.write_text(yaml_content)
    lib = load_library(p)
    assert len(lib) == 1
    assert lib["test_mat"].density_g_cm3 == pytest.approx(3.14)


def test_load_malformed_yaml_raises(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text("materials:\n  - group_id: x\n")
    with pytest.raises((ValueError, Exception)):
        load_library(p)
