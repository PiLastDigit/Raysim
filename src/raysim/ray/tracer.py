"""Iterative closest-hit traversal with material-state stack accumulator.

Phase A.4. The core ∑ρL accumulator that turns a :class:`~raysim.ray.scene.BuiltScene`
plus a batch of ray (origin, direction) pairs into per-ray ``∑ρL`` (g/cm²) and
diagnostic counts.

Algorithm overview (see ``MVP_STEPS.md`` §A.4 and ``docs/decisions/phase-0.md``):

  1. Closest-hit query at the active rays' current advance positions.
  2. **Segment contribution** ``t_local × Σ ρ_s × 0.1`` (mm → cm) accumulates
     into ``∑ρL`` *before* the stack is mutated.
  3. **Tie batch.** Look up the hit primitive's tied-group id (built in
     :mod:`raysim.ray.scene`). All members are processed in one zero-length
     batch, sorted by ``(geom_id, prim_id)`` ascending — deterministic.
  4. **Stack updates.** For each batch member, ``dot(direction, normal) < 0``
     ⇒ entry (push); ``> 0`` ⇒ exit (pop). Mismatches (push when already in
     stack, pop on absent solid) are counted but do not abort.
  5. **eps gap correction.** After updating, add ``eps × Σ ρ_s × 0.1`` for the
     post-batch stack — accounting for the small physical region we'll skip
     when advancing the origin by ``t_local + eps``.
  6. Advance ``cur_origin ← cur_origin + direction × (t_local + eps)`` and
     repeat. ``eps = 1e-6 × bbox_diag``.

Termination invariants:

  * Stack non-empty at miss ⇒ geometry leak ⇒ ``stack_leak[i] = True``.
  * Cumulative in-stack chord exceeding ``bbox_diag_mm`` ⇒
    ``overlap_suspicious[i] = True``.
  * Iteration count ``> max_hits`` ⇒ ``max_hit_exceeded[i] = True``; CLI
    treats this as run-fatal.

The float64 chord-length accumulator runs on the Python side: ``tfar`` is
upcast to float64 immediately. ``MVP_STEPS.md §A.7`` hard-gates the impact
on the concentric-shell test at relative error ≤ 1e-5.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import structlog
from numpy.typing import NDArray

from raysim.ray.scene import BuiltScene

_LOG = structlog.get_logger(__name__)

DEFAULT_MAX_HITS = 4096


@dataclass(frozen=True)
class TraversalResult:
    """Per-ray output of :func:`trace_rays`."""

    sigma_rho_l_g_cm2: NDArray[np.float64]
    n_hits: NDArray[np.int32]
    n_tangent_grazes: NDArray[np.int32]
    mismatch_counts: NDArray[np.int32]
    stack_leak: NDArray[np.bool_]
    overlap_suspicious: NDArray[np.bool_]
    max_hit_exceeded: NDArray[np.bool_]


def trace_rays(
    scene: BuiltScene,
    origins_mm: NDArray[np.float64],
    directions: NDArray[np.float64],
    *,
    max_hits: int = DEFAULT_MAX_HITS,
    epsilon_mm: float | None = None,
    initial_stack: tuple[int, ...] = (),
) -> TraversalResult:
    """Run the iterative closest-hit accumulator on a batch of rays.

    Parameters
    ----------
    scene :
        Pre-built scene from :func:`raysim.ray.scene.load_scene_from_directory`.
    origins_mm :
        ``(N, 3)`` float64 ray origins, in mm.
    directions :
        ``(N, 3)`` float64 ray direction unit vectors.
    max_hits :
        Per-ray safety cap. Exceeding sets ``max_hit_exceeded[i] = True`` —
        callers should treat that as run-fatal.
    epsilon_mm :
        Override for the ``tnear`` advance; defaults to
        ``1e-6 × scene.bbox_diag_mm`` per ``MVP_PLAN.md §3``.
    initial_stack :
        Geom-ids of solids the rays are *initially inside*. Use this when
        emitting rays from a detector position contained within one or more
        solids — the seeded stack ensures the first segment contributes its
        chord-through-the-enclosing-solid correctly. See
        :func:`enclosing_solids` for the standard probe.
    """
    if origins_mm.ndim != 2 or origins_mm.shape[1] != 3:
        raise ValueError(f"origins_mm shape must be (N, 3), got {origins_mm.shape}")
    if directions.shape != origins_mm.shape:
        raise ValueError("directions shape must match origins_mm")

    n_rays = int(origins_mm.shape[0])
    eps = float(epsilon_mm if epsilon_mm is not None else 1e-6 * scene.bbox_diag_mm)
    bbox_diag = float(scene.bbox_diag_mm)

    densities = scene.density_per_geom  # (n_geoms,)
    tied_ids_per_geom = scene.tied_group_id_per_geom
    tied_members = scene.tied_group_members
    normals_per_geom = scene.triangle_normals_per_geom

    sigma_rho_l = np.zeros(n_rays, dtype=np.float64)
    n_hits = np.zeros(n_rays, dtype=np.int32)
    n_tangent_grazes = np.zeros(n_rays, dtype=np.int32)
    mismatch_counts = np.zeros(n_rays, dtype=np.int32)
    stack_leak = np.zeros(n_rays, dtype=bool)
    overlap_suspicious = np.zeros(n_rays, dtype=bool)
    max_hit_exceeded = np.zeros(n_rays, dtype=bool)
    in_stack_chord_mm = np.zeros(n_rays, dtype=np.float64)

    # Per-ray stack, as a Python list of geom_ids. Stack depth is bounded by
    # the number of distinct solids the ray is simultaneously inside, which
    # is typically 1–2 (and at most ~5 even in heavy assemblies).
    stacks: list[list[int]] = [list(initial_stack) for _ in range(n_rays)]

    # Embree consumes float32 vertices and float32 ray origins/directions. We
    # advance origins in float32 because that's what's queryable; chord-length
    # accumulation stays float64.
    cur_origins_f32 = origins_mm.astype(np.float32, copy=True)
    dirs_f32 = directions.astype(np.float32, copy=False)
    active = np.ones(n_rays, dtype=bool)

    iteration = 0
    while active.any() and iteration < max_hits:
        iteration += 1
        active_idx = np.flatnonzero(active)
        result = scene.embree_scene.run(  # type: ignore[attr-defined]
            cur_origins_f32[active_idx],
            dirs_f32[active_idx],
            query="INTERSECT",
            output=True,
        )
        prim_ids = np.asarray(result["primID"], dtype=np.int64)
        geom_ids = np.asarray(result["geomID"], dtype=np.int64)
        tfar = np.asarray(result["tfar"], dtype=np.float64)

        miss_mask = prim_ids < 0
        if miss_mask.any():
            miss_global = active_idx[miss_mask]
            for gi in miss_global:
                if stacks[gi]:
                    stack_leak[gi] = True
                active[gi] = False

        hit_mask = ~miss_mask
        hit_local_idx = np.flatnonzero(hit_mask)
        for li in hit_local_idx:
            gi = int(active_idx[li])
            t_local = float(tfar[li])
            geom_id = int(geom_ids[li])
            prim_id = int(prim_ids[li])

            stack = stacks[gi]
            # Segment contribution (pre-batch stack), mm → cm via ×0.1.
            if stack:
                seg_density = float(np.sum(densities[stack]))
                sigma_rho_l[gi] += t_local * 0.1 * seg_density
                in_stack_chord_mm[gi] += t_local
                if in_stack_chord_mm[gi] > bbox_diag:
                    overlap_suspicious[gi] = True

            # Build tie batch.
            tied_id = int(tied_ids_per_geom[geom_id][prim_id])
            if tied_id < 0:
                batch: tuple[tuple[int, int], ...] = ((geom_id, prim_id),)
            else:
                batch = tied_members[tied_id]

            ray_dir = directions[gi]
            for g_b, p_b in batch:
                normal = normals_per_geom[g_b][p_b]
                d = float(np.dot(ray_dir, normal))
                if d < 0.0:
                    # Entry. Mismatch if g_b already in stack; still push.
                    if g_b in stack:
                        mismatch_counts[gi] += 1
                    stack.append(g_b)
                elif d > 0.0:
                    # Exit. Mismatch if g_b not in stack.
                    if g_b in stack:
                        stack.remove(g_b)
                    else:
                        mismatch_counts[gi] += 1
                else:
                    # Tangent grazing — no surface event, no stack change.
                    n_tangent_grazes[gi] += 1

            # Eps-gap correction: the small region [t_hit, t_hit + eps] has
            # the post-batch stack and is skipped when we advance the origin.
            if stack:
                seg_density_after = float(np.sum(densities[stack]))
                sigma_rho_l[gi] += eps * 0.1 * seg_density_after

            n_hits[gi] += 1

            # Advance origin by (t_local + eps) along direction. Float32
            # arithmetic; cur_origins_f32 stays a (N,3) float32 array.
            advance = np.float32(t_local + eps)
            cur_origins_f32[gi] = cur_origins_f32[gi] + dirs_f32[gi] * advance

    if iteration >= max_hits and active.any():
        # Some rays exhausted the safety cap. CLI converts this to run-fatal.
        max_hit_exceeded[active] = True
        _LOG.error(
            "ray.tracer.max_hits_exceeded",
            n_rays_capped=int(active.sum()),
            max_hits=max_hits,
        )

    return TraversalResult(
        sigma_rho_l_g_cm2=sigma_rho_l,
        n_hits=n_hits,
        n_tangent_grazes=n_tangent_grazes,
        mismatch_counts=mismatch_counts,
        stack_leak=stack_leak,
        overlap_suspicious=overlap_suspicious,
        max_hit_exceeded=max_hit_exceeded,
    )


def enclosing_solids(
    scene: BuiltScene, point_mm: NDArray[np.float64]
) -> tuple[int, ...]:
    """Return the geom-ids of the solids that *contain* ``point_mm``.

    Used to seed :func:`trace_rays`'s ``initial_stack`` for detectors placed
    inside a solid. Without this seeding, the first hit on every emitted ray
    is an exit on an empty stack — a stack-mismatch event — and the chord
    through the enclosing solid is silently uncounted.

    Implementation: cast a single probe ray from a known-outside point along
    the line through ``point_mm``. Iterative closest-hit, advancing along the
    line, capping when accumulated ``t`` reaches the distance to ``point_mm``.
    The stack state at termination is the enclosing set.

    The probe is direction-agnostic — any choice of "outside" works as long
    as the ray clears the scene bbox. We use ``-X`` past the bbox by ten
    diagonals.
    """
    bbox_min = np.asarray(scene.bbox_min_mm, dtype=np.float64)
    bbox_max = np.asarray(scene.bbox_max_mm, dtype=np.float64)
    pad = 10.0 * scene.bbox_diag_mm
    far_origin = np.array([bbox_min[0] - pad, bbox_max[1] + pad, bbox_max[2] + pad])
    direction = (point_mm - far_origin)
    total_dist = float(np.linalg.norm(direction))
    if total_dist <= 0.0:
        return ()
    direction /= total_dist

    eps = float(1e-6 * scene.bbox_diag_mm)
    densities_unused = scene.density_per_geom  # noqa: F841 (only stack is needed here)
    tied_ids_per_geom = scene.tied_group_id_per_geom
    tied_members = scene.tied_group_members
    normals_per_geom = scene.triangle_normals_per_geom

    cur_origin = far_origin.astype(np.float32, copy=True)[None, :]
    direction_f32 = direction.astype(np.float32, copy=False)[None, :]
    stack: list[int] = []
    accumulated_t = 0.0

    for _ in range(DEFAULT_MAX_HITS):
        result = scene.embree_scene.run(  # type: ignore[attr-defined]
            cur_origin, direction_f32, query="INTERSECT", output=True
        )
        prim_id = int(result["primID"][0])
        if prim_id < 0:
            break
        t_local = float(result["tfar"][0])
        if accumulated_t + t_local >= total_dist:
            # The next hit lies past the detector position; we're done — the
            # current stack is the enclosing set.
            break
        geom_id = int(result["geomID"][0])

        tied_id = int(tied_ids_per_geom[geom_id][prim_id])
        batch: tuple[tuple[int, int], ...] = (
            ((geom_id, prim_id),) if tied_id < 0 else tied_members[tied_id]
        )

        for g_b, p_b in batch:
            normal = normals_per_geom[g_b][p_b]
            d = float(np.dot(direction, normal))
            if d < 0.0:
                stack.append(g_b)
            elif d > 0.0 and g_b in stack:
                stack.remove(g_b)
        accumulated_t += t_local + eps
        cur_origin = cur_origin + direction_f32 * np.float32(t_local + eps)

    return tuple(sorted(set(stack)))
