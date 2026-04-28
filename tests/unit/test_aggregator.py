"""Phase A.5: per-detector aggregation."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("embreex")

from raysim.dose import RHO_AL_REF_G_CM3, aggregate_detector, build_dose_spline
from raysim.env.importers.omere_dos import import_omere_dos
from raysim.proj.schema import Detector, Material
from raysim.ray import load_scene_from_directory

ROOT = Path(__file__).resolve().parents[2]
GEOM = ROOT / "benchmarks" / "geometries"
FIXTURE = ROOT / "tests" / "fixtures" / "dose700km.dos"

MATS = [
    Material(group_id="aluminum", density_g_cm3=2.70),
    Material(group_id="copper", density_g_cm3=8.96),
]


@pytest.fixture(scope="module")
def spline():  # type: ignore[no-untyped-def]
    return build_dose_spline(import_omere_dos(FIXTURE))


def test_uniform_sphere_dose_matches_ddc_lookup(spline) -> None:  # type: ignore[no-untyped-def]
    """A point detector at the center of a uniform Al sphere should see the
    DDC's interpolated value at that thickness, since *every* HEALPix ray
    crosses the same chord (2R for a centered detector).

    MVP_PLAN §6 Phase A acceptance #2: ±0.1% on the DDC's value at t."""
    scene = load_scene_from_directory(GEOM / "solid_sphere", MATS)
    det = Detector(name="center", position_xyz_mm=(0.0, 0.0, 0.0))
    res = aggregate_detector(scene, spline, det, nside=8)

    # Sphere R=50 mm; every ray exits through one wall, chord = R = 50 mm of Al.
    expected_sigma_rho_l = 50.0 * 0.1 * 2.70  # 13.5 g/cm²
    expected_mm_al = expected_sigma_rho_l / RHO_AL_REF_G_CM3 * 10.0  # 50 mm
    expected_dose = float(spline.dose_total(expected_mm_al))

    assert res.sigma_rho_l_mean_g_cm2 == pytest.approx(expected_sigma_rho_l, rel=1e-3)
    assert res.mm_al_equivalent_mean == pytest.approx(expected_mm_al, rel=1e-3)
    # The dose-lookup tolerance is the dominant term; the spline reproduces the
    # source DDC at the deepest sample to ≤1% (per A.2). Use 1% rel here so
    # that both spline noise and uv_sphere discretization fit comfortably.
    assert res.dose_total_krad == pytest.approx(expected_dose, rel=1e-2)


def test_aluminum_box_detector_centered(spline) -> None:  # type: ignore[no-untyped-def]
    scene = load_scene_from_directory(GEOM / "aluminum_box", MATS)
    det = Detector(name="center", position_xyz_mm=(0.0, 0.0, 0.0))
    res = aggregate_detector(scene, spline, det, nside=8)
    # Min equivalent thickness is along principal axes (50 mm Al = 50 mm-Al-eq).
    # Max is along corner (50*sqrt(3) ≈ 86.6 mm Al).
    assert res.shielding_pctile_mm_al.min == pytest.approx(50.0, abs=0.5)
    assert res.shielding_pctile_mm_al.max == pytest.approx(50.0 * np.sqrt(3), abs=2.0)
    assert res.shielding_pctile_mm_al.median > 50.0
    assert res.angular_spread_mm_al > 0.0
    # No diagnostics on a clean single-solid scene.
    assert res.n_stack_leak_rays == 0
    assert res.n_max_hit_rays == 0


def test_per_species_sum_close_to_total(spline) -> None:  # type: ignore[no-untyped-def]
    """Per-species breakdown (canonical + extras) must reconcile with the total
    to OMERE's print precision. Floor is ~5e-3: OMERE writes 4 sig figs, so
    the species-vs-total ledger can't be tighter than that."""
    scene = load_scene_from_directory(GEOM / "aluminum_box", MATS)
    det = Detector(name="center", position_xyz_mm=(0.0, 0.0, 0.0))
    res = aggregate_detector(scene, spline, det, nside=8)
    species_total = sum(res.dose_per_species_krad.values())
    rel = abs(species_total - res.dose_total_krad) / max(res.dose_total_krad, 1e-30)
    assert rel < 5e-3


def test_extra_species_appear_in_breakdown(spline) -> None:  # type: ignore[no-untyped-def]
    """Regression for the reviewer-flagged dropped-species bug: OMERE's
    non-canonical columns (``other_electrons``, ``other_protons``,
    ``other_gamma_photons``) must appear in ``dose_per_species_krad`` whenever
    the source DDC carried them. Otherwise the per-species sum cannot
    reconcile with ``dose_total``."""
    scene = load_scene_from_directory(GEOM / "aluminum_box", MATS)
    det = Detector(name="d", position_xyz_mm=(0.0, 0.0, 0.0))
    res = aggregate_detector(scene, spline, det, nside=8)
    keys = set(res.dose_per_species_krad.keys())
    assert "other_electrons" in keys
    assert "other_protons" in keys
    assert "other_gamma_photons" in keys


def test_pixel_map_emit_toggle(spline) -> None:  # type: ignore[no-untyped-def]
    scene = load_scene_from_directory(GEOM / "aluminum_box", MATS)
    det = Detector(name="d", position_xyz_mm=(0.0, 0.0, 0.0))
    res_off = aggregate_detector(scene, spline, det, nside=8, emit_pixel_map=False)
    assert res_off.healpix_mm_al_per_pixel is None
    res_on = aggregate_detector(scene, spline, det, nside=8, emit_pixel_map=True)
    assert res_on.healpix_mm_al_per_pixel is not None
    assert len(res_on.healpix_mm_al_per_pixel) == 12 * 8 * 8


def test_box_detector_not_supported_in_stage_a(spline) -> None:  # type: ignore[no-untyped-def]
    scene = load_scene_from_directory(GEOM / "aluminum_box", MATS)
    det = Detector(
        name="b", position_xyz_mm=(0, 0, 0), kind="box", box_extents_mm=(1.0, 1.0, 1.0)
    )
    with pytest.raises(NotImplementedError):
        aggregate_detector(scene, spline, det, nside=8)
