"""Phase A.2: log-cubic dose spline + edge-case handling."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from raysim.dose import build_dose_spline
from raysim.env.importers.omere_dos import import_omere_dos
from raysim.env.schema import DoseDepthCurve

FIXTURE = Path(__file__).parent.parent / "fixtures" / "dose700km.dos"


# --- Real DDC (round-trip ≤1% per source row, MVP_STEPS §A.2 done-when) -----


@pytest.fixture(scope="module")
def real_spline():  # type: ignore[no-untyped-def]
    return build_dose_spline(import_omere_dos(FIXTURE))


def test_real_total_round_trips(real_spline) -> None:  # type: ignore[no-untyped-def]
    ddc = import_omere_dos(FIXTURE)
    t = np.asarray(ddc.thickness_mm_al)
    d_truth = np.asarray(ddc.dose_total)
    d_back = real_spline.dose_total(t)
    rel = np.abs(d_back - d_truth) / np.maximum(d_truth, 1e-30)
    assert rel.max() < 0.01, f"max round-trip {rel.max():.3%}"


def test_real_per_species_round_trips(real_spline) -> None:  # type: ignore[no-untyped-def]
    ddc = import_omere_dos(FIXTURE)
    t = np.asarray(ddc.thickness_mm_al)
    for name, col in ddc.dose_per_species.items():
        d_truth = np.asarray(col)
        nz = d_truth > 0
        if nz.sum() < 4:
            continue
        d_back = real_spline.dose_species(name, t)
        rel = np.abs(d_back - d_truth)[nz] / d_truth[nz]
        assert rel.max() < 0.01, f"{name}: {rel.max():.3%}"


def test_clamps_below_t_min(real_spline) -> None:  # type: ignore[no-untyped-def]
    t_min = real_spline.t_min_mm_al
    d_at_min = float(real_spline.dose_total(t_min))
    # Anything below t_min reads as the t_min value, not -inf or extrapolated.
    d_below = real_spline.dose_total(0.5 * t_min)
    assert float(d_below) == pytest.approx(d_at_min, rel=1e-12)
    assert real_spline.extrapolation_warnings.get("total:below_t_min", 0) >= 1


def test_zero_thickness_clamped_silently(real_spline) -> None:  # type: ignore[no-untyped-def]
    """t = 0 is the dominant case for empty-LOS rays. It must clamp to D(t_min)
    without spamming the warning counter."""
    pre = real_spline.extrapolation_warnings.get("total:below_t_min", 0)
    out = real_spline.dose_total(np.zeros(100))
    assert np.allclose(out, real_spline.dose_total(real_spline.t_min_mm_al))
    post = real_spline.extrapolation_warnings.get("total:below_t_min", 0)
    assert post == pre


def test_clamps_above_t_max(real_spline) -> None:  # type: ignore[no-untyped-def]
    t_max = real_spline.t_max_mm_al
    d_at_max = float(real_spline.dose_total(t_max))
    d_above = real_spline.dose_total(2.0 * t_max)
    assert float(d_above) == pytest.approx(d_at_max, rel=1e-12)


# --- Synthetic edge-case DDCs ----------------------------------------------


def _synthetic_ddc(
    thickness: list[float],
    dose_total: list[float],
    species: dict[str, list[float]] | None = None,
) -> DoseDepthCurve:
    return DoseDepthCurve(
        thickness_mm_al=tuple(thickness),
        dose_per_species={k: tuple(v) for k, v in (species or {}).items()},
        dose_total=tuple(dose_total),
        source_tool="synthetic",
    )


def test_extra_species_get_their_own_spline() -> None:
    """Reviewer regression: a DDC where ``extra_species`` carries a
    non-trivial fraction of the dose must (a) expose those extras in
    :attr:`DoseSpline.species_names`, and (b) reconcile with the total via
    ``sum(per-species) ≈ total`` at every queried thickness.

    Construction note: every column shares the same power law so each
    column is a perfect line in (log t, log D) and the spline reproduces it
    to numerical noise. The total is the sum of those columns; because they
    share the exponent, the total is *also* a power law and likewise spline-
    exact. This lets the reconciliation be tested at numerical precision —
    a looser tolerance would mask the very bug under test."""
    t = np.array([0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0])
    base = 200.0 * t ** (-1.4)
    canonical_e = 0.30 * base
    canonical_p = 0.20 * base
    extra_other_p = 0.30 * base  # > canonical electrons — must NOT be dropped
    extra_other_e = 0.20 * base
    total = base
    ddc = DoseDepthCurve(
        thickness_mm_al=tuple(t.tolist()),
        dose_per_species={
            "trapped_electron": tuple(canonical_e.tolist()),
            "trapped_proton": tuple(canonical_p.tolist()),
        },
        dose_total=tuple(total.tolist()),
        extra_species={
            "other_protons": tuple(extra_other_p.tolist()),
            "other_electrons": tuple(extra_other_e.tolist()),
        },
        source_tool="synthetic-extras",
    )
    sp = build_dose_spline(ddc)
    assert "other_protons" in sp.species_names
    assert "other_electrons" in sp.species_names

    t_query = np.array([0.7, 1.3, 2.5, 5.0, 10.0, 20.0])
    total_back = sp.dose_total(t_query)
    species_back = sum(sp.dose_species(name, t_query) for name in sp.species_names)
    rel = np.abs(species_back - total_back) / total_back
    assert rel.max() < 1e-9, f"per-species sum drifts from total by {rel.max():.3e}"


def test_pure_zero_species_returns_zero() -> None:
    """A canonical species column that is all zero ⇒ constant-zero callable,
    no log transform attempted (MVP_STEPS §A.2 second edge case)."""
    ddc = _synthetic_ddc(
        thickness=[1.0, 2.0, 4.0, 8.0],
        dose_total=[100.0, 50.0, 25.0, 12.5],
        species={"gamma": [0.0, 0.0, 0.0, 0.0]},
    )
    sp = build_dose_spline(ddc)
    out = sp.dose_species("gamma", np.array([1.0, 3.0, 5.0]))
    assert np.all(out == 0.0)


def test_mixed_zero_species_floor() -> None:
    """A species column with mixed zero/nonzero is fit on a floored copy.
    Below the deepest nonzero entry, the floor reads as ~0; above, it tracks
    the spline within tolerance."""
    ddc = _synthetic_ddc(
        thickness=[1.0, 2.0, 4.0, 8.0, 16.0],
        dose_total=[100.0, 50.0, 25.0, 12.5, 6.25],
        # Trapped electrons drop out at deeper thickness — common OMERE pattern.
        species={"trapped_electron": [80.0, 40.0, 20.0, 0.0, 0.0]},
    )
    sp = build_dose_spline(ddc)
    # At known nonzero points, the spline reproduces.
    e1 = float(sp.dose_species("trapped_electron", 1.0))
    assert e1 == pytest.approx(80.0, rel=1e-3)
    # At a floored thickness, the result is near the floor (i.e. ≪ any real dose).
    e_deep = float(sp.dose_species("trapped_electron", 8.0))
    assert e_deep < 1e-6


def test_log_log_recovers_exponential() -> None:
    """A pure exponential D = D0 * exp(-α t) is a *line* in (log t, log D)?
    No — it's a line in (t, log D). Use a power law instead: D = a t^-k is a
    line in (log t, log D), which the log-cubic spline must recover exactly."""
    t_grid = np.array([0.5, 1.0, 2.0, 4.0, 8.0, 16.0])
    a, k = 1000.0, 1.5
    d_grid = a * t_grid ** (-k)
    ddc = _synthetic_ddc(thickness=t_grid.tolist(), dose_total=d_grid.tolist())
    sp = build_dose_spline(ddc)
    t_query = np.array([0.7, 1.3, 2.5, 5.0, 10.0])
    d_truth = a * t_query ** (-k)
    d_back = sp.dose_total(t_query)
    rel = np.abs(d_back - d_truth) / d_truth
    # A cubic spline on a perfectly-linear log-log function should be ~exact.
    assert rel.max() < 1e-6


def test_negative_t_clamps_and_counts() -> None:
    ddc = _synthetic_ddc(thickness=[1.0, 2.0, 4.0, 8.0], dose_total=[10.0, 5.0, 2.5, 1.25])
    sp = build_dose_spline(ddc)
    out = sp.dose_total(np.array([-1.0, -2.0, 1.0, 2.0]))
    # Negatives clamped to t_min ⇒ D(t_min) = 10.0; nonneg query unaffected.
    assert out[0] == pytest.approx(10.0, rel=1e-12)
    assert out[1] == pytest.approx(10.0, rel=1e-12)
    assert sp.extrapolation_warnings.get("total:negative_t", 0) == 2


def test_monotonicity_breach_logs_not_fatal() -> None:
    """Small forward bumps in the *total* column are tolerated (MVP_STEPS §A.2)."""
    # Forward bump: D[2] > D[1].
    ddc = _synthetic_ddc(thickness=[1.0, 2.0, 4.0, 8.0], dose_total=[10.0, 4.9, 5.0, 2.5])
    sp = build_dose_spline(ddc)
    # Spline still fits; query the bumpy region.
    out = sp.dose_total(np.array([1.5, 3.0]))
    assert np.all(np.isfinite(out))
