"""Per-detector aggregation — Phase A.5.

Drives the HEALPix ray emission from a detector position, hands the rays to
:func:`raysim.ray.trace_rays`, converts ∑ρL → mm-Al-equivalent, and aggregates
per-pixel dose lookups into a :class:`raysim.proj.schema.DetectorResult`.

Statistic naming follows ``MVP_STEPS.md §A.5`` strictly: the per-pixel spread
across the HEALPix sphere is :data:`angular_spread_mm_al` — a *deterministic*
diagnostic of how much shielding varies by direction. It is **not** a Monte
Carlo σ. The output schema deliberately uses no field named ``sigma`` or
``±σ`` to keep that distinction load-bearing.
"""

from __future__ import annotations

import numpy as np
import structlog
from numpy.typing import NDArray

from raysim.dose.spline import DoseSpline
from raysim.proj.schema import Detector, DetectorResult, ShieldingPercentiles
from raysim.ray.healpix import all_pixel_directions, npix_for_nside
from raysim.ray.scene import BuiltScene
from raysim.ray.tracer import enclosing_solids, trace_rays

_LOG = structlog.get_logger(__name__)

#: Aluminum reference density used for the mm-Al-equivalent conversion. Per
#: ``MVP_PLAN.md §3`` this is the standard sector-analysis approximation
#: (``t_Al = ∑ρL / ρ_Al``), accurate to ~10–20 % across most low-Z spacecraft
#: materials. Documented value is the Al-6061 nominal density used by the
#: seeded material library; the conversion uses *this* fixed reference
#: regardless of which Al alloy any given solid in the scene uses.
RHO_AL_REF_G_CM3 = 2.70


def aggregate_detector(
    scene: BuiltScene,
    spline: DoseSpline,
    detector: Detector,
    *,
    nside: int,
    emit_pixel_map: bool = False,
) -> DetectorResult:
    """Run HEALPix ray emission from ``detector`` and aggregate.

    Parameters
    ----------
    scene :
        Pre-built Embree scene.
    spline :
        Pre-built dose spline (total + per species).
    detector :
        Detector position + name. Box detectors are not supported in Stage A
        (cloud-of-subdetectors lands in Stage B per ``MVP_PLAN §4.9``).
    nside :
        HEALPix resolution. ``npix = 12 × Nside²``.
    emit_pixel_map :
        When ``True``, the full per-pixel mm-Al-equivalent map is included in
        the result. Off by default to keep output sizes modest.
    """
    if detector.kind != "point":
        raise NotImplementedError(
            f"Stage A only supports point detectors; got kind={detector.kind!r}. "
            "Box detectors land in Stage B per MVP_PLAN §4.9."
        )

    npix = npix_for_nside(nside)
    dirs = all_pixel_directions(nside)  # (npix, 3) float64
    origin = np.asarray(detector.position_xyz_mm, dtype=np.float64)
    origins = np.broadcast_to(origin, (npix, 3)).copy()

    # Detectors placed inside one or more solids need their per-ray stack
    # seeded so the chord through the enclosing material counts in ∑ρL.
    # This is the standard sector-analysis case: the detector is a chip
    # inside the spacecraft, surrounded by structure on all sides.
    seed = enclosing_solids(scene, origin)
    if seed:
        _LOG.debug(
            "dose.aggregate.detector_enclosed",
            detector=detector.name,
            seed_geom_ids=list(seed),
        )

    trav = trace_rays(scene, origins, dirs, initial_stack=seed)

    # ∑ρL → mm-Al-equivalent.
    # ∑ρL [g/cm²] / ρ_Al [g/cm³] = thickness [cm]; ×10 → mm.
    sigma_rho_l = trav.sigma_rho_l_g_cm2  # (npix,) float64
    mm_al = (sigma_rho_l / RHO_AL_REF_G_CM3) * 10.0  # mm

    # Per-pixel dose lookup. Spline is log-cubic on (log t, log D).
    dose_total_per_pixel = spline.dose_total(mm_al)  # (npix,) krad
    dose_total_mean = float(np.mean(dose_total_per_pixel))

    dose_per_species: dict[str, float] = {}
    for sp_name in spline.species_names:
        d_per_pixel = spline.dose_species(sp_name, mm_al)
        dose_per_species[sp_name] = float(np.mean(d_per_pixel))

    # Shielding distribution stats — over mm-Al-equivalent.
    pct = ShieldingPercentiles(
        min=float(np.min(mm_al)),
        p05=float(np.percentile(mm_al, 5)),
        median=float(np.median(mm_al)),
        p95=float(np.percentile(mm_al, 95)),
        max=float(np.max(mm_al)),
    )
    angular_spread = float(np.std(mm_al))

    # Run-health counters.
    n_stack_leak = int(np.sum(trav.stack_leak))
    n_overlap_susp = int(np.sum(trav.overlap_suspicious))
    n_max_hit = int(np.sum(trav.max_hit_exceeded))
    n_mismatch_events = int(np.sum(trav.mismatch_counts))

    pixel_map: tuple[float, ...] | None = None
    if emit_pixel_map:
        pixel_map = tuple(float(x) for x in mm_al.tolist())

    if n_stack_leak or n_max_hit or n_overlap_susp or n_mismatch_events:
        _LOG.warning(
            "dose.aggregate.diagnostics",
            detector=detector.name,
            n_stack_leak=n_stack_leak,
            n_overlap_suspicious=n_overlap_susp,
            n_max_hit=n_max_hit,
            n_mismatch_events=n_mismatch_events,
        )

    return DetectorResult(
        detector_name=detector.name,
        n_pixels=npix,
        sigma_rho_l_mean_g_cm2=float(np.mean(sigma_rho_l)),
        mm_al_equivalent_mean=float(np.mean(mm_al)),
        dose_total_krad=dose_total_mean,
        dose_per_species_krad=dose_per_species,
        angular_spread_mm_al=angular_spread,
        shielding_pctile_mm_al=pct,
        n_overlap_suspicious_rays=n_overlap_susp,
        n_stack_leak_rays=n_stack_leak,
        n_stack_mismatch_events=n_mismatch_events,
        n_max_hit_rays=n_max_hit,
        healpix_mm_al_per_pixel=pixel_map,
    )


def mass_per_unit_solid_angle(sigma_rho_l: NDArray[np.float64]) -> float:
    """Convenience: HEALPix-equal-area solid-angle integral check.

    ∑ρL is a mass-thickness, not a true mass-per-unit-solid-angle, but the
    HEALPix unweighted mean over all 12·Nside² directions multiplied by 4π
    gives the integrated 'mass-thickness × steradian' quantity used in the
    A.7 mass-conservation sanity test. See ``MVP_STEPS.md §A.5``.
    """
    return float(np.mean(sigma_rho_l)) * 4.0 * float(np.pi)
