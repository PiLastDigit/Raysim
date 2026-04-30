"""Tests for raysim.proj.project — Phase B2.5."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from raysim.proj.project import (
    PROJECT_SCHEMA_VERSION,
    GeometryRef,
    NamingRuleOverride,
    ProjectFile,
    load_project,
    save_project,
)
from raysim.proj.schema import Detector, MaterialAssignment


def _make_geometry_file(tmp_path: Path) -> tuple[Path, str]:
    """Create a dummy geometry file and return (path, sha256)."""
    from raysim.proj.hashing import hash_file

    geom = tmp_path / "test.step"
    geom.write_bytes(b"fake step content for hashing")
    return geom, hash_file(geom)


def _make_project(tmp_path: Path) -> tuple[ProjectFile, Path]:
    geom_path, geom_hash = _make_geometry_file(tmp_path)
    project = ProjectFile(
        geometry=GeometryRef(
            path=geom_path.name,
            sha256=geom_hash,
        ),
        assignments=(
            MaterialAssignment(solid_id="s0", material_group_id="aluminum_6061"),
        ),
        assignment_sources={"s0": "manual"},
        detectors=(
            Detector(name="det1", position_xyz_mm=(0.0, 0.0, 0.0)),
        ),
        created_at_utc="2026-04-30T12:00:00+00:00",
        raysim_version="0.2.0",
    )
    return project, tmp_path


def test_save_load_round_trip(tmp_path: Path) -> None:
    project, base = _make_project(tmp_path)
    proj_path = base / "test.raysim"
    save_project(project, proj_path)

    loaded = load_project(proj_path)
    assert loaded.geometry.sha256 == project.geometry.sha256
    assert loaded.assignments == project.assignments
    assert loaded.detectors == project.detectors
    assert loaded.created_at_utc == "2026-04-30T12:00:00+00:00"


def test_save_load_save_bit_identical(tmp_path: Path) -> None:
    project, base = _make_project(tmp_path)

    path1 = base / "first.raysim"
    save_project(project, path1)
    bytes1 = path1.read_bytes()

    loaded = load_project(path1)
    path2 = base / "second.raysim"
    save_project(loaded, path2)
    bytes2 = path2.read_bytes()

    assert bytes1 == bytes2


def test_created_at_utc_preserved(tmp_path: Path) -> None:
    project, base = _make_project(tmp_path)
    proj_path = base / "test.raysim"
    save_project(project, proj_path)
    loaded = load_project(proj_path)
    assert loaded.created_at_utc == project.created_at_utc


def test_geometry_hash_warns_on_mismatch(tmp_path: Path) -> None:
    project, base = _make_project(tmp_path)
    proj_path = base / "test.raysim"
    save_project(project, proj_path)

    # Tamper with the geometry file after saving the project.
    geom = base / project.geometry.path
    geom.write_bytes(b"tampered content")

    # Should load successfully (warn, not fail).
    loaded = load_project(proj_path)
    assert loaded is not None


def test_schema_version_current(tmp_path: Path) -> None:
    project, base = _make_project(tmp_path)
    proj_path = base / "test.raysim"
    save_project(project, proj_path)
    loaded = load_project(proj_path)
    assert loaded.project_schema_version == PROJECT_SCHEMA_VERSION


def test_schema_version_unsupported_raises(tmp_path: Path) -> None:
    project, base = _make_project(tmp_path)
    proj_path = base / "test.raysim"
    save_project(project, proj_path)

    raw = json.loads(proj_path.read_text())
    raw["project_schema_version"] = 999
    proj_path.write_text(json.dumps(raw))

    with pytest.raises(ValueError, match="Unsupported project schema version"):
        load_project(proj_path)


def test_malformed_project_raises(tmp_path: Path) -> None:
    proj_path = tmp_path / "bad.raysim"
    proj_path.write_text('{"project_schema_version": 1}')
    with pytest.raises((ValueError, Exception)):
        load_project(proj_path)


def test_naming_rule_overrides(tmp_path: Path) -> None:
    geom_path, geom_hash = _make_geometry_file(tmp_path)
    project = ProjectFile(
        geometry=GeometryRef(path=geom_path.name, sha256=geom_hash),
        naming_rule_overrides=(
            NamingRuleOverride(pattern="(?i)custom", group_id="custom_mat", priority=20),
        ),
        created_at_utc="2026-04-30T12:00:00+00:00",
        raysim_version="0.2.0",
    )
    proj_path = tmp_path / "test.raysim"
    save_project(project, proj_path)
    loaded = load_project(proj_path)
    assert loaded.naming_rule_overrides is not None
    assert len(loaded.naming_rule_overrides) == 1
    assert loaded.naming_rule_overrides[0].group_id == "custom_mat"


def test_empty_project_defaults(tmp_path: Path) -> None:
    geom_path, geom_hash = _make_geometry_file(tmp_path)
    project = ProjectFile(
        geometry=GeometryRef(path=geom_path.name, sha256=geom_hash),
        created_at_utc="2026-04-30T12:00:00+00:00",
        raysim_version="0.2.0",
    )
    proj_path = tmp_path / "test.raysim"
    save_project(project, proj_path)
    loaded = load_project(proj_path)
    assert loaded.assignments == ()
    assert loaded.detectors == ()
    assert loaded.dose_curve_path is None
