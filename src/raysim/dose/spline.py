"""Log-cubic spline over a :class:`~raysim.env.schema.DoseDepthCurve`.

Phase A.2. Builds SciPy ``CubicSpline`` instances on ``(log t, log D)`` for the
total-dose column and each per-species column. Public API:

  * :func:`build_dose_spline` — returns an opaque :class:`DoseSpline` keyed by
    species name (``"total"``, plus every canonical key in
    :data:`raysim.env.schema.CANONICAL_SPECIES`).
  * :class:`DoseSpline.dose_total(mm_al)` and ``.dose_species(name, mm_al)``
    return ``krad(Si)`` for a 1-D array of mm-Al-equivalent thicknesses.

Edge cases handled per MVP_STEPS §A.2:
  * ``t = 0`` and ``t < t_min``: clamp to ``D(t_min)`` with a warning. The DDC
    starts at a small but nonzero thickness; extrapolating into ``log(0)``
    silently produces wrong physics.
  * ``t > t_max``: clamp to ``D(t_max)`` with a warning. (Direct LOS rays in
    open scenes can have ∑ρL deeper than the imported DDC's deepest sample;
    this is rare but legal.)
  * Pure-zero species column: returns a constant-zero callable (no log, no
    spline).
  * Mixed-zero species column: floor zeros to ``ZERO_FLOOR_KRAD`` (1e-30 krad)
    before the log, fit on the floored data; results below the floor read as
    near-zero on output. The floor is documented in the spline metadata.
  * Monotonicity of total-dose: input is *expected* to be monotonically
    decreasing in t; small forward bumps are logged but not fatal.

The ``DoseSpline`` carries the source DDC's ``mission_metadata`` and a hash of
the canonical DDC payload, so callers (CLI, reports) can attach scenario
provenance without re-parsing the .dos file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import structlog
from numpy.typing import ArrayLike, NDArray
from scipy.interpolate import CubicSpline

from raysim.env.schema import CANONICAL_SPECIES, DoseDepthCurve

_LOG = structlog.get_logger(__name__)

#: Floor applied to zero entries in mixed-zero species columns before the log
#: transform. Below this value, results are effectively zero. The choice is
#: deep enough that no real DDC's smallest nonzero entry hits the floor.
ZERO_FLOOR_KRAD = 1e-30


@dataclass(frozen=True)
class _SpeciesSpline:
    """One species' spline + clamp bounds (or a constant-zero sentinel)."""

    is_zero: bool
    spline: CubicSpline | None
    t_min_log: float
    t_max_log: float
    d_at_t_min: float
    d_at_t_max: float
    n_zero_floored: int  # how many entries were floored before fitting


@dataclass(frozen=True)
class DoseSpline:
    """Built from a :class:`DoseDepthCurve`. Thread-safe (all numpy/SciPy
    objects are read-only after construction).

    Attributes
    ----------
    t_min_mm_al, t_max_mm_al :
        Source DDC thickness bounds. Queries outside ``[t_min, t_max]`` are
        clamped (with a counted warning) instead of extrapolated.
    extrapolation_warnings :
        Mutable counter for how many ``__call__`` queries were clamped.
        Useful for surfacing in the run report; not part of the deterministic
        output stream.

    Per-species coverage: every column the source DDC carries — both canonical
    keys (:data:`raysim.env.schema.CANONICAL_SPECIES`) and dialect-specific
    extras (:attr:`DoseDepthCurve.extra_species`, e.g. OMERE's
    ``other_electrons`` / ``other_protons`` / ``other_gamma_photons``) — gets
    its own log-cubic spline. The aggregator iterates :attr:`species_names`
    so the per-species breakdown reconciles with ``dose_total`` for any DDC
    where extras carry a meaningful fraction of the dose.
    """

    t_min_mm_al: float
    t_max_mm_al: float
    _total: _SpeciesSpline
    _species: dict[str, _SpeciesSpline]
    canonical_species: frozenset[str]
    extra_species: frozenset[str]
    mission_metadata: dict[str, Any] = field(default_factory=dict)
    source_tool: str = ""
    extrapolation_warnings: dict[str, int] = field(default_factory=dict)

    # ----- public lookups ----------------------------------------------------

    def dose_total(self, mm_al: ArrayLike) -> NDArray[np.float64]:
        """Total-dose lookup, krad(Si)."""
        return self._eval(self._total, np.asarray(mm_al, dtype=np.float64), key="total")

    def dose_species(self, name: str, mm_al: ArrayLike) -> NDArray[np.float64]:
        """Per-species lookup. ``name`` must appear in
        :attr:`species_names` — that includes canonical keys *and* any
        dialect-specific extras the source DDC carried."""
        sp = self._species.get(name)
        if sp is None:
            raise KeyError(f"unknown species {name!r}; known: {sorted(self._species)}")
        return self._eval(sp, np.asarray(mm_al, dtype=np.float64), key=name)

    @property
    def species_names(self) -> tuple[str, ...]:
        """All species columns the spline was fit for, sorted. Includes both
        canonical and extra species; the aggregator iterates this so the
        per-species breakdown reconciles with the total."""
        return tuple(sorted(self._species.keys()))

    # ----- internals ---------------------------------------------------------

    def _eval(
        self, sp: _SpeciesSpline, mm_al: NDArray[np.float64], *, key: str
    ) -> NDArray[np.float64]:
        if sp.is_zero:
            return np.zeros_like(mm_al)
        # Negative t is invalid input; clamp to t_min and count it. (∑ρL is
        # always non-negative, so this only triggers on caller bugs.)
        if np.any(mm_al < 0):
            self.extrapolation_warnings[f"{key}:negative_t"] = (
                self.extrapolation_warnings.get(f"{key}:negative_t", 0) + int(np.sum(mm_al < 0))
            )
        t = np.maximum(mm_al, 0.0)
        # Floor below t_min and clamp above t_max — exclude exactly ``t = 0``
        # from the floor-warning count (it's the dominant case for empty-LOS
        # rays and we don't want the diagnostic to light up on every clean run).
        below = t < self.t_min_mm_al
        above = t > self.t_max_mm_al
        n_below_nonzero = int(np.sum(below & (t > 0)))
        n_above = int(np.sum(above))
        if n_below_nonzero:
            self.extrapolation_warnings[f"{key}:below_t_min"] = (
                self.extrapolation_warnings.get(f"{key}:below_t_min", 0) + n_below_nonzero
            )
        if n_above:
            self.extrapolation_warnings[f"{key}:above_t_max"] = (
                self.extrapolation_warnings.get(f"{key}:above_t_max", 0) + n_above
            )
        # Compute log(t) for the in-range part, evaluate spline, exp() back.
        t_clamped = np.clip(t, self.t_min_mm_al, self.t_max_mm_al)
        log_t = np.log(t_clamped)
        assert sp.spline is not None  # not is_zero ⇒ spline is set
        log_d = sp.spline(log_t)
        d = np.exp(log_d)
        # Patch in the explicit clamp values where we hit the boundary, so
        # below_min queries return the deepest documented dose (the spline at
        # the boundary equals D(t_min) up to numerical noise, but be exact).
        d = np.where(below, sp.d_at_t_min, d)
        d = np.where(above, sp.d_at_t_max, d)
        return d.astype(np.float64, copy=False)


def build_dose_spline(ddc: DoseDepthCurve) -> DoseSpline:
    """Build a :class:`DoseSpline` from a :class:`DoseDepthCurve`."""
    t_arr = np.asarray(ddc.thickness_mm_al, dtype=np.float64)
    if t_arr[0] <= 0:
        # Schema permits ``t == 0`` for the first sample; the log-spline can't.
        # Real OMERE files start at small nonzero t, so this is defensive.
        raise ValueError(
            "DDC thickness must start at strictly positive value for log-cubic fit"
        )

    log_t = np.log(t_arr)
    t_min = float(t_arr[0])
    t_max = float(t_arr[-1])

    total_arr = np.asarray(ddc.dose_total, dtype=np.float64)
    _check_monotonic(total_arr, "total")
    total_sp = _fit_log_log(log_t, total_arr, name="total", t_min=t_min, t_max=t_max)

    species_splines: dict[str, _SpeciesSpline] = {}
    for sp_name in CANONICAL_SPECIES:
        col = ddc.dose_per_species.get(sp_name)
        if col is None:
            # Missing canonical species ⇒ all zeros, no-op spline.
            species_splines[sp_name] = _SpeciesSpline(
                is_zero=True,
                spline=None,
                t_min_log=float(log_t[0]),
                t_max_log=float(log_t[-1]),
                d_at_t_min=0.0,
                d_at_t_max=0.0,
                n_zero_floored=0,
            )
            continue
        species_splines[sp_name] = _fit_log_log(
            log_t, np.asarray(col, dtype=np.float64), name=sp_name, t_min=t_min, t_max=t_max
        )

    # Dialect-specific extras (e.g. OMERE's other_electrons / other_protons /
    # other_gamma_photons): the source DDC's ``dose_total`` includes these
    # columns, so the per-species breakdown must too. The schema validator
    # forbids name collisions between ``CANONICAL_SPECIES`` and
    # ``extra_species``, so this insert is always disjoint.
    for extra_name, extra_col in ddc.extra_species.items():
        species_splines[extra_name] = _fit_log_log(
            log_t,
            np.asarray(extra_col, dtype=np.float64),
            name=extra_name,
            t_min=t_min,
            t_max=t_max,
        )

    return DoseSpline(
        t_min_mm_al=t_min,
        t_max_mm_al=t_max,
        _total=total_sp,
        _species=species_splines,
        canonical_species=frozenset(CANONICAL_SPECIES),
        extra_species=frozenset(ddc.extra_species.keys()),
        mission_metadata=dict(ddc.mission_metadata),
        source_tool=ddc.source_tool,
    )


def _fit_log_log(
    log_t: NDArray[np.float64],
    d: NDArray[np.float64],
    *,
    name: str,
    t_min: float,
    t_max: float,
) -> _SpeciesSpline:
    if d.shape != log_t.shape:
        raise ValueError(f"{name}: dose array shape {d.shape} != thickness {log_t.shape}")
    if np.all(d == 0.0):
        # Pure-zero column: skip the spline entirely.
        return _SpeciesSpline(
            is_zero=True,
            spline=None,
            t_min_log=float(log_t[0]),
            t_max_log=float(log_t[-1]),
            d_at_t_min=0.0,
            d_at_t_max=0.0,
            n_zero_floored=0,
        )
    n_zero = int(np.sum(d == 0.0))
    if n_zero:
        d = np.where(d > 0, d, ZERO_FLOOR_KRAD)
        _LOG.info("dose.spline.zero_floor", species=name, n_floored=n_zero, floor=ZERO_FLOOR_KRAD)
    log_d = np.log(d)
    # CubicSpline: extrapolate=False, we always clamp at our boundary.
    cs = CubicSpline(log_t, log_d, extrapolate=False)
    return _SpeciesSpline(
        is_zero=False,
        spline=cs,
        t_min_log=float(log_t[0]),
        t_max_log=float(log_t[-1]),
        d_at_t_min=float(d[0]),
        d_at_t_max=float(d[-1]),
        n_zero_floored=n_zero,
    )


def _check_monotonic(d: NDArray[np.float64], name: str) -> None:
    """Log (don't fail) if a *total*-dose column has small forward bumps.

    Per MVP_STEPS §A.2: 'OMERE DDCs are monotonically decreasing within a
    species but not strictly so when summed (rare numerical jitter).' We keep
    fitting; the warning surfaces in the report.
    """
    diffs = np.diff(d)
    n_up = int(np.sum(diffs > 0))
    if n_up:
        _LOG.info(
            "dose.spline.monotonicity_breach",
            column=name,
            n_forward_bumps=n_up,
            max_bump=float(np.max(diffs[diffs > 0])),
        )
