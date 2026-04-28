"""Phase A: CLI loader unit tests — CSV vs YAML materials, assignments file."""

from __future__ import annotations

from pathlib import Path

import pytest

from raysim.cli.run import _load_assignments, _load_detectors, _load_materials


def test_load_materials_csv(tmp_path: Path) -> None:
    p = tmp_path / "materials.csv"
    p.write_text(
        "group_id,density_g_cm3,z_eff,display_name\n"
        "aluminum,2.70,13.0,Al 6061\n"
        "copper,8.96,29.0,Cu\n",
        encoding="utf-8",
    )
    out = _load_materials(p)
    assert {m.group_id for m in out} == {"aluminum", "copper"}
    assert next(m for m in out if m.group_id == "copper").density_g_cm3 == pytest.approx(8.96)


def test_load_materials_yaml(tmp_path: Path) -> None:
    """YAML support is documented in the CLI; pyyaml must be a runtime
    dependency. This test ensures both the loader path and the dep wiring
    survive a refactor."""
    p = tmp_path / "materials.yaml"
    p.write_text(
        "materials:\n"
        "  - group_id: aluminum\n"
        "    density_g_cm3: 2.70\n"
        "    z_eff: 13.0\n"
        "    display_name: Al 6061\n"
        "  - group_id: copper\n"
        "    density_g_cm3: 8.96\n"
        "    z_eff: 29.0\n",
        encoding="utf-8",
    )
    out = _load_materials(p)
    assert {m.group_id for m in out} == {"aluminum", "copper"}


def test_load_materials_yaml_top_level_list(tmp_path: Path) -> None:
    """Bare list form (no top-level 'materials' key) is also accepted."""
    p = tmp_path / "materials.yml"
    p.write_text(
        "- group_id: titanium\n"
        "  density_g_cm3: 4.51\n",
        encoding="utf-8",
    )
    out = _load_materials(p)
    assert out[0].group_id == "titanium"


def test_load_detectors_dict_form(tmp_path: Path) -> None:
    p = tmp_path / "det.json"
    p.write_text(
        '{"detectors": [{"name": "d1", "position_xyz_mm": [0, 0, 0]}]}',
        encoding="utf-8",
    )
    out = _load_detectors(p)
    assert out[0].name == "d1"


def test_load_detectors_top_level_list(tmp_path: Path) -> None:
    p = tmp_path / "det.json"
    p.write_text('[{"name": "d1", "position_xyz_mm": [1, 2, 3]}]', encoding="utf-8")
    out = _load_detectors(p)
    assert out[0].position_xyz_mm == (1.0, 2.0, 3.0)


def test_load_assignments_none_returns_empty(tmp_path: Path) -> None:
    """``--assignments`` omitted ⇒ empty list. The hash of the empty list is
    canonical; the loader's "solid_id == material_group_id" fallback fires."""
    assert _load_assignments(None) == []


def test_load_assignments_top_level_list(tmp_path: Path) -> None:
    p = tmp_path / "as.json"
    p.write_text(
        '[{"solid_id": "panel", "material_group_id": "gaas"}]', encoding="utf-8"
    )
    out = _load_assignments(p)
    assert len(out) == 1
    assert out[0].solid_id == "panel"
    assert out[0].material_group_id == "gaas"
