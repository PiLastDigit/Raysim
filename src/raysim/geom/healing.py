"""Healing and shell-orientation normalization — Phase B1.3.

Two passes per solid:

1. ``BRepMesh_ModelHealer`` operates on the ``TopoDS_Solid`` handle (in-place
   triangulation update), then the triangulation is re-extracted.
2. Shell-orientation normalization via per-shell probe rays.  Convention:
   every triangle's normal points **out of solid material** — into vacuum
   for outer shells, into the cavity void for cavity shells.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import structlog
from numpy.typing import NDArray

from raysim.geom.tessellation import TessellatedShell, TessellatedSolid

_LOG = structlog.get_logger(__name__)

_TANGENT_TOL = 1e-9
_PROBE_DIRECTIONS = [
    np.array([1.0, 0.0, 0.0]),
    np.array([0.0, 1.0, 0.0]),
    np.array([0.0, 0.0, 1.0]),
]


class ShellRole(StrEnum):
    OUTER = "outer"
    CAVITY = "cavity"


@dataclass(frozen=True)
class HealedShell:
    """A shell after healing and orientation normalization."""

    shell_index: int
    vertices: NDArray[np.float64]
    faces: NDArray[np.int64]
    triangle_normals: NDArray[np.float64]
    role: ShellRole
    was_flipped: bool


@dataclass(frozen=True)
class HealedSolid:
    """Per-solid post-healing record."""

    solid_id: str
    shells: tuple[HealedShell, ...]
    bbox_min_mm: tuple[float, float, float]
    bbox_max_mm: tuple[float, float, float]


def heal_assembly(
    solids: Sequence[TessellatedSolid],
) -> tuple[HealedSolid, ...]:
    """Run healing + shell-orientation normalization on all solids."""
    return tuple(_heal_one(s) for s in solids)


def _heal_one(solid: TessellatedSolid) -> HealedSolid:
    """Heal a single tessellated solid."""
    shells = _run_healer_and_reextract(solid)
    roles = _classify_shell_roles(shells)
    healed_shells = _normalize_orientations(shells, roles, solid)

    return HealedSolid(
        solid_id=solid.solid_id,
        shells=tuple(healed_shells),
        bbox_min_mm=solid.bbox_min_mm,
        bbox_max_mm=solid.bbox_max_mm,
    )


def _run_healer_and_reextract(
    solid: TessellatedSolid,
) -> list[TessellatedShell]:
    """Run BRepMesh_ModelHealer on the shape and re-extract triangulation."""
    try:
        from OCC.Core.BRepMesh import BRepMesh_ModelHealer

        healer = BRepMesh_ModelHealer()
        healer.Perform(solid.shape)
        _LOG.debug("healing.healer_done", solid_id=solid.solid_id)
    except (ImportError, AttributeError, TypeError):
        _LOG.debug("healing.healer_skipped", solid_id=solid.solid_id,
                    reason="BRepMesh_ModelHealer not available or not callable")

    from raysim.geom.tessellation import _extract_shells

    return _extract_shells(solid.shape)


def _classify_shell_roles(
    shells: list[TessellatedShell],
) -> list[ShellRole]:
    """Classify each shell as OUTER or CAVITY.

    Single-shell solids: the single shell is OUTER.
    Multi-shell: the shell whose vertex centroid is not contained by any
    other shell is OUTER; rest are CAVITY.
    """
    if len(shells) == 1:
        return [ShellRole.OUTER]

    centroids = [s.vertices.mean(axis=0) for s in shells]
    roles: list[ShellRole] = []

    for i, _shell_i in enumerate(shells):
        is_contained = False
        for j, shell_j in enumerate(shells):
            if i == j:
                continue
            if _point_in_shell(centroids[i], shell_j):
                is_contained = True
                break
        roles.append(ShellRole.CAVITY if is_contained else ShellRole.OUTER)

    n_outer = sum(1 for r in roles if r == ShellRole.OUTER)
    if n_outer != 1:
        _LOG.warning(
            "healing.ambiguous_outer",
            n_outer=n_outer,
            n_shells=len(shells),
        )
        if n_outer == 0 and roles:
            roles[0] = ShellRole.OUTER

    return roles


def _point_in_shell(
    point: NDArray[np.float64],
    shell: TessellatedShell,
) -> bool:
    """Test if a point is inside a shell using odd-crossing ray cast."""
    direction = np.array([1.0, 0.0, 0.0])
    crossings = 0
    verts = shell.vertices
    faces = shell.faces

    for tri_idx in range(faces.shape[0]):
        v0 = verts[faces[tri_idx, 0]]
        v1 = verts[faces[tri_idx, 1]]
        v2 = verts[faces[tri_idx, 2]]
        t = _ray_triangle_intersect(point, direction, v0, v1, v2)
        if t is not None and t > 0:
            crossings += 1

    return crossings % 2 == 1


def _ray_triangle_intersect(
    origin: NDArray[np.float64],
    direction: NDArray[np.float64],
    v0: NDArray[np.float64],
    v1: NDArray[np.float64],
    v2: NDArray[np.float64],
) -> float | None:
    """Möller–Trumbore ray-triangle intersection, returns t or None."""
    edge1 = v1 - v0
    edge2 = v2 - v0
    h = np.cross(direction, edge2)
    a = np.dot(edge1, h)
    if abs(a) < 1e-12:
        return None
    f = 1.0 / a
    s = origin - v0
    u = f * np.dot(s, h)
    if u < 0.0 or u > 1.0:
        return None
    q = np.cross(s, edge1)
    v = f * np.dot(direction, q)
    if v < 0.0 or u + v > 1.0:
        return None
    t = f * np.dot(edge2, q)
    return float(t) if t > 1e-12 else None


def _normalize_orientations(
    shells: list[TessellatedShell],
    roles: list[ShellRole],
    solid: TessellatedSolid,
) -> list[HealedShell]:
    """Per-shell probe rays to verify and fix orientation."""
    all_verts, all_faces, shell_id_per_tri = _combine_shells(shells)
    bbox_min = np.array(solid.bbox_min_mm)
    bbox_max = np.array(solid.bbox_max_mm)
    bbox_diag = float(np.linalg.norm(bbox_max - bbox_min))

    result: list[HealedShell] = []

    for i, (shell, role) in enumerate(zip(shells, roles, strict=True)):
        centroid = shell.vertices.mean(axis=0)
        was_flipped = False

        for probe_dir in _PROBE_DIRECTIONS:
            origin = centroid - probe_dir * (bbox_diag + 10.0)
            direction = probe_dir.copy()

            first_dot = _probe_first_hit_dot(
                origin, direction, all_verts, all_faces, shell_id_per_tri, i
            )
            if first_dot is None:
                continue

            needs_flip = False
            if role == ShellRole.OUTER:
                # First hit on outer shell should be entry (dot < 0).
                if first_dot > 0:
                    needs_flip = True
            else:
                # First hit on cavity shell should be exit (dot > 0) —
                # ray going from solid material into cavity.
                if first_dot < 0:
                    needs_flip = True

            if needs_flip:
                shell = _flip_shell(shell)
                all_verts, all_faces, shell_id_per_tri = _combine_shells(
                    [s if idx != i else shell for idx, s in enumerate(shells)]
                )
                shells[i] = shell
                was_flipped = True
                _LOG.info(
                    "healing.shell_flipped",
                    solid_id=solid.solid_id,
                    shell_index=i,
                    role=role,
                )

                # Re-verify: full entry/exit sequence, stack returns to zero.
                if not _verify_probe_sequence(
                    origin, direction, all_verts, all_faces, shell_id_per_tri,
                    shells, roles,
                ):
                    _LOG.error(
                        "healing.reverify_failed",
                        solid_id=solid.solid_id,
                        shell_index=i,
                        role=role,
                    )

            break
        else:
            _LOG.warning(
                "healing.no_valid_probe",
                solid_id=solid.solid_id,
                shell_index=i,
            )

        result.append(HealedShell(
            shell_index=shell.shell_index,
            vertices=shell.vertices,
            faces=shell.faces,
            triangle_normals=shell.triangle_normals,
            role=role,
            was_flipped=was_flipped,
        ))

    return result


def _combine_shells(
    shells: list[TessellatedShell],
) -> tuple[NDArray[np.float64], NDArray[np.int64], NDArray[np.int32]]:
    """Combine all shells into a single vertex/face array for probe rays."""
    if not shells:
        return (
            np.empty((0, 3), dtype=np.float64),
            np.empty((0, 3), dtype=np.int64),
            np.empty(0, dtype=np.int32),
        )

    all_verts_list: list[NDArray[np.float64]] = []
    all_faces_list: list[NDArray[np.int64]] = []
    shell_ids: list[int] = []
    vert_offset = 0

    for i, shell in enumerate(shells):
        all_verts_list.append(shell.vertices)
        all_faces_list.append(shell.faces + vert_offset)
        shell_ids.extend([i] * shell.faces.shape[0])
        vert_offset += shell.vertices.shape[0]

    return (
        np.vstack(all_verts_list),
        np.vstack(all_faces_list),
        np.array(shell_ids, dtype=np.int32),
    )


def _verify_probe_sequence(
    origin: NDArray[np.float64],
    direction: NDArray[np.float64],
    all_verts: NDArray[np.float64],
    all_faces: NDArray[np.int64],
    shell_id_per_tri: NDArray[np.int32],
    shells: list[TessellatedShell],
    roles: list[ShellRole],
) -> bool:
    """Verify entry/exit sequence along a probe ray; stack must return to zero."""
    hits: list[tuple[float, float, int]] = []  # (t, dot, shell_idx)

    for tri_idx in range(all_faces.shape[0]):
        v0 = all_verts[all_faces[tri_idx, 0]]
        v1 = all_verts[all_faces[tri_idx, 1]]
        v2 = all_verts[all_faces[tri_idx, 2]]
        t = _ray_triangle_intersect(origin, direction, v0, v1, v2)
        if t is not None and t > 0:
            edge1 = v1 - v0
            edge2 = v2 - v0
            normal = np.cross(edge1, edge2)
            norm_len = np.linalg.norm(normal)
            if norm_len > 0:
                normal = normal / norm_len
            dot_val = float(np.dot(direction, normal))
            if abs(dot_val) < _TANGENT_TOL:
                continue
            hits.append((t, dot_val, int(shell_id_per_tri[tri_idx])))

    if not hits:
        return True

    hits.sort(key=lambda h: h[0])

    stack_count = 0
    for _t, dot_val, _shell_idx in hits:
        if dot_val < 0:
            stack_count += 1  # entry
        else:
            stack_count -= 1  # exit

    return stack_count == 0


def _probe_first_hit_dot(
    origin: NDArray[np.float64],
    direction: NDArray[np.float64],
    all_verts: NDArray[np.float64],
    all_faces: NDArray[np.int64],
    shell_id_per_tri: NDArray[np.int32],
    target_shell: int,
) -> float | None:
    """Cast a probe ray and return dot(direction, normal) of the first hit
    on the target shell, or None if no valid hit."""
    best_t: float | None = None
    best_dot: float | None = None

    for tri_idx in range(all_faces.shape[0]):
        if shell_id_per_tri[tri_idx] != target_shell:
            continue
        v0 = all_verts[all_faces[tri_idx, 0]]
        v1 = all_verts[all_faces[tri_idx, 1]]
        v2 = all_verts[all_faces[tri_idx, 2]]
        t = _ray_triangle_intersect(origin, direction, v0, v1, v2)
        if t is not None and t > 0:
            edge1 = v1 - v0
            edge2 = v2 - v0
            normal = np.cross(edge1, edge2)
            norm_len = np.linalg.norm(normal)
            if norm_len > 0:
                normal = normal / norm_len
            dot_val = float(np.dot(direction, normal))
            if abs(dot_val) < _TANGENT_TOL:
                continue
            if best_t is None or t < best_t:
                best_t = t
                best_dot = dot_val

    return best_dot


def _flip_shell(shell: TessellatedShell) -> TessellatedShell:
    """Reverse triangle winding and recompute normals."""
    flipped_faces = shell.faces[:, ::-1].copy()
    v0 = shell.vertices[flipped_faces[:, 0]]
    v1 = shell.vertices[flipped_faces[:, 1]]
    v2 = shell.vertices[flipped_faces[:, 2]]
    n = np.cross(v1 - v0, v2 - v0)
    norm = np.linalg.norm(n, axis=1, keepdims=True)
    norm = np.where(norm == 0, 1.0, norm)
    normals = (n / norm).astype(np.float64, copy=False)

    return TessellatedShell(
        shell_index=shell.shell_index,
        vertices=shell.vertices,
        faces=flipped_faces,
        triangle_normals=normals,
    )
