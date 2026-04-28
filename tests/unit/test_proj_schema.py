"""Phase A.1: project schemas + canonical JSON serialization."""

from __future__ import annotations

import json
import math

import pytest
from pydantic import ValidationError

from raysim.proj import (
    Detector,
    DetectorResult,
    Material,
    MaterialAssignment,
    Provenance,
    RunResult,
    ShieldingPercentiles,
)
from raysim.proj.canonical_json import dumps as canonical_dumps
from raysim.proj.hashing import hash_canonical


def test_material_round_trip() -> None:
    m = Material(group_id="aluminum", density_g_cm3=2.70, z_eff=13.0, display_name="Al 6061")
    rt = Material.model_validate_json(m.model_dump_json())
    assert rt == m


def test_material_density_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Material(group_id="al", density_g_cm3=0.0)


def test_detector_box_requires_extents() -> None:
    with pytest.raises(ValidationError):
        Detector(name="d1", position_xyz_mm=(0, 0, 0), kind="box")


def test_detector_box_extents_only_when_box() -> None:
    with pytest.raises(ValidationError):
        Detector(
            name="d1",
            position_xyz_mm=(0, 0, 0),
            kind="point",
            box_extents_mm=(1.0, 1.0, 1.0),
        )


def test_detector_default_frame_is_identity() -> None:
    d = Detector(name="d1", position_xyz_mm=(1.0, 2.0, 3.0))
    assert d.frame_axes == ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def test_run_result_round_trip() -> None:
    prov = Provenance(
        raysim_version="0.0.1",
        nside=8,
        epsilon_mm=1e-3,
        bbox_diag_mm=200.0,
        geometry_hash="0" * 64,
        materials_hash="1" * 64,
        assignments_hash="2" * 64,
        detectors_hash="3" * 64,
        dose_curve_hash="4" * 64,
    )
    pct = ShieldingPercentiles(min=0.5, p05=0.6, median=1.0, p95=2.0, max=3.0)
    det = DetectorResult(
        detector_name="d1",
        n_pixels=768,
        sigma_rho_l_mean_g_cm2=2.7,
        mm_al_equivalent_mean=10.0,
        dose_total_krad=12.5,
        dose_per_species_krad={"trapped_electron": 5.0, "trapped_proton": 7.5},
        angular_spread_mm_al=0.1,
        shielding_pctile_mm_al=pct,
    )
    rr = RunResult(detectors=(det,), provenance=prov)
    rt = RunResult.model_validate_json(rr.model_dump_json())
    assert rt == rr


# --- Canonical JSON ---------------------------------------------------------


def test_canonical_dumps_keys_sorted() -> None:
    s = canonical_dumps({"b": 1, "a": 2}, indent=False)
    assert s == '{"a":2,"b":1}'


def test_canonical_dumps_floats_round_trip() -> None:
    # 0.1 + 0.2 != 0.3, but %.17g preserves the exact bit pattern.
    x = 0.1 + 0.2
    s = canonical_dumps(x, indent=False)
    rt = json.loads(s)
    assert rt == x


def test_canonical_dumps_integer_floats_keep_dot() -> None:
    s = canonical_dumps(1.0, indent=False)
    assert s == "1.0"


def test_canonical_dumps_handles_non_finite() -> None:
    s = canonical_dumps(math.inf, indent=False)
    assert s == '"Infinity"'
    s = canonical_dumps(-math.inf, indent=False)
    assert s == '"-Infinity"'
    s = canonical_dumps(math.nan, indent=False)
    assert s == '"NaN"'


def test_canonical_dumps_tuple_as_list() -> None:
    s = canonical_dumps((1.0, 2.0), indent=False)
    assert s == "[1.0,2.0]"


def test_canonical_dumps_nested_pretty() -> None:
    out = canonical_dumps({"x": [1, 2], "y": {"a": 1.0}}, indent=True)
    expected = (
        "{\n"
        '  "x": [\n'
        "    1,\n"
        "    2\n"
        "  ],\n"
        '  "y": {\n'
        '    "a": 1.0\n'
        "  }\n"
        "}"
    )
    assert out == expected


def test_hash_canonical_stable_across_dict_order() -> None:
    h1 = hash_canonical({"a": 1, "b": 2})
    h2 = hash_canonical({"b": 2, "a": 1})
    assert h1 == h2


def test_assignment_smoke() -> None:
    a = MaterialAssignment(solid_id="aluminum", material_group_id="aluminum")
    assert a.solid_id == "aluminum"
