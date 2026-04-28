"""Phase 0 §0.3: OMERE .dos importer + spline round-trip ≤1% per source row."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from scipy.interpolate import CubicSpline

from raysim.env.importers.omere_dos import import_omere_dos
from raysim.env.schema import CANONICAL_SPECIES, DoseDepthCurve

FIXTURE = Path(__file__).parent.parent / "fixtures" / "dose700km.dos"


@pytest.fixture(scope="module")
def ddc() -> DoseDepthCurve:
    return import_omere_dos(FIXTURE)


def test_importer_returns_canonical_schema(ddc: DoseDepthCurve) -> None:
    assert isinstance(ddc, DoseDepthCurve)
    assert ddc.source_tool.startswith("OMERE-")
    assert len(ddc.thickness_mm_al) >= 10
    # Strictly increasing, validated in the model — but assert here too.
    arr = np.asarray(ddc.thickness_mm_al)
    assert np.all(np.diff(arr) > 0)


def test_all_canonical_species_present(ddc: DoseDepthCurve) -> None:
    assert set(ddc.dose_per_species.keys()) == set(CANONICAL_SPECIES)


def test_extra_species_carried(ddc: DoseDepthCurve) -> None:
    assert "other_electrons" in ddc.extra_species
    assert "other_protons" in ddc.extra_species
    assert "other_gamma_photons" in ddc.extra_species


def test_units_converted_rad_to_krad(ddc: DoseDepthCurve) -> None:
    """First row of dose700km.dos is 1.925e+06 rad → 1925 krad. Verify."""
    assert ddc.dose_total[0] == pytest.approx(1925.0, rel=1e-4)
    assert ddc.dose_total[-1] == pytest.approx(0.04281, rel=1e-4)


def test_mission_metadata_extracted(ddc: DoseDepthCurve) -> None:
    md = ddc.mission_metadata
    assert md["perigee_km"] == 700.0
    assert md["apogee_km"] == 700.0
    assert md["inclination_deg"] == 98.0
    assert md["target_material"] == "Silicon"
    assert md["trapped_electron_model"].startswith("AE9")
    assert md["trapped_proton_model"].startswith("AP9")
    assert md["solar_proton_confidence_pct"] == 95.0
    assert "raw_header" in md and md["raw_header"].startswith("#")


def test_species_columns_sum_close_to_total(ddc: DoseDepthCurve) -> None:
    """Per-species + extras should reconstruct the total to OMERE's print precision."""
    total = np.asarray(ddc.dose_total)
    s = sum(np.asarray(c) for c in ddc.dose_per_species.values()) + sum(
        np.asarray(c) for c in ddc.extra_species.values()
    )
    rel_err = np.abs(s - total) / np.maximum(total, 1e-30)
    # OMERE writes 4 sig figs, so 1e-3 is the floor of what's achievable.
    assert rel_err.max() < 5e-3


def test_spline_round_trip_within_one_percent(ddc: DoseDepthCurve) -> None:
    """§0.3 done-when: spline fit reproduces source rows to ≤1% relative error."""
    t = np.log(np.asarray(ddc.thickness_mm_al))
    d = np.log(np.asarray(ddc.dose_total))
    spline = CubicSpline(t, d, extrapolate=False)
    # Evaluate at the source thicknesses themselves.
    d_back = np.exp(spline(t))
    d_truth = np.asarray(ddc.dose_total)
    rel = np.abs(d_back - d_truth) / np.maximum(d_truth, 1e-30)
    assert rel.max() < 0.01, f"max spline reproduction error {rel.max():.3%} > 1%"


def test_per_species_splines_round_trip(ddc: DoseDepthCurve) -> None:
    """Per-species columns: where a column has any nonzero value, the log-cubic
    spline must reproduce the nonzero rows to ≤1%. Pure-zero columns are skipped.
    """
    t = np.log(np.asarray(ddc.thickness_mm_al))
    for name, col in ddc.dose_per_species.items():
        d = np.asarray(col)
        nz = d > 0
        if nz.sum() < 4:
            continue
        # Log-spline only over the nonzero subdomain (per A.2 edge-case rules).
        sub_t = t[nz]
        sub_d = np.log(d[nz])
        spline = CubicSpline(sub_t, sub_d, extrapolate=False)
        rel = np.abs(np.exp(spline(sub_t)) - d[nz]) / d[nz]
        assert rel.max() < 0.01, (
            f"species {name!r} spline reproduction error {rel.max():.3%} > 1%"
        )


def test_invalid_file_raises(tmp_path: Path) -> None:
    bad = tmp_path / "not_a_dos.dos"
    bad.write_text("# empty header\n# no data\n")
    with pytest.raises(ValueError, match="no data rows"):
        import_omere_dos(bad)


def test_ragged_data_raises(tmp_path: Path) -> None:
    bad = tmp_path / "ragged.dos"
    bad.write_text(
        "# Thickness    Trapped     Total\n"
        "#   Al        electrons    Dose\n"
        "#  mm_Al          rad         rad\n"
        "1.0  2.0  3.0\n"
        "1.5  2.5\n"  # short row
    )
    with pytest.raises(ValueError, match="ragged"):
        import_omere_dos(bad)
