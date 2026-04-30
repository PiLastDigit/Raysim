"""Tests for raysim.mat.gating — Phase B2.6."""

from __future__ import annotations

import pytest

from raysim.mat.gating import check_density_anomalies, check_run_readiness
from raysim.mat.library import _build_library
from raysim.proj.schema import Material, MaterialAssignment


@pytest.fixture()
def lib() -> object:
    return _build_library([
        Material(group_id="al", density_g_cm3=2.70),
        Material(group_id="cu", density_g_cm3=8.96),
    ])


def test_ready_when_complete(lib: object) -> None:
    assignments = [
        MaterialAssignment(solid_id="s0", material_group_id="al"),
        MaterialAssignment(solid_id="s1", material_group_id="cu"),
    ]
    result = check_run_readiness(assignments, ["s0", "s1"], lib)  # type: ignore[arg-type]
    assert result.ready
    assert result.missing_solids == ()
    assert result.unresolved_assignments == ()


def test_missing_solid(lib: object) -> None:
    assignments = [MaterialAssignment(solid_id="s0", material_group_id="al")]
    result = check_run_readiness(assignments, ["s0", "s1"], lib)  # type: ignore[arg-type]
    assert not result.ready
    assert "s1" in result.missing_solids


def test_unresolved_assignment(lib: object) -> None:
    assignments = [MaterialAssignment(solid_id="s0", material_group_id="nonexistent")]
    result = check_run_readiness(assignments, ["s0"], lib)  # type: ignore[arg-type]
    assert not result.ready
    assert "s0" in result.unresolved_assignments


def test_density_anomaly_low() -> None:
    mats = [Material(group_id="foam", density_g_cm3=0.1)]
    anomalies = check_density_anomalies(mats)
    assert len(anomalies) == 1
    assert anomalies[0].kind == "low"


def test_density_anomaly_high() -> None:
    mats = [Material(group_id="osmium", density_g_cm3=25.1)]
    anomalies = check_density_anomalies(mats)
    assert len(anomalies) == 1
    assert anomalies[0].kind == "high"


def test_density_at_boundary_not_flagged() -> None:
    mats = [
        Material(group_id="low_edge", density_g_cm3=0.5),
        Material(group_id="high_edge", density_g_cm3=25.0),
    ]
    anomalies = check_density_anomalies(mats)
    assert len(anomalies) == 0


def test_density_normal_not_flagged() -> None:
    mats = [Material(group_id="al", density_g_cm3=2.70)]
    anomalies = check_density_anomalies(mats)
    assert len(anomalies) == 0
