"""Per-shell watertightness validation — Phase B1.4.

Checks each healed shell for edge-pair consistency: every non-degenerate edge
must appear in exactly two triangles with opposite vertex orders.

OCCT face triangulations have per-face node tables — adjacent faces do not
share vertex indices even when coordinates coincide.  Before building the edge
map, vertices are merged within a coordinate tolerance (``1e-9 mm``) by
rounding to a grid and remapping indices.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import structlog

from raysim.geom.healing import HealedSolid

_LOG = structlog.get_logger(__name__)

VERTEX_MERGE_TOL_MM = 1e-9


@dataclass(frozen=True)
class ShellWatertightness:
    """Watertightness result for a single shell."""

    shell_index: int
    pass_: bool
    unpaired_edges: tuple[tuple[int, int], ...]
    same_orientation_edges: tuple[tuple[int, int], ...]
    degenerate_triangles: tuple[int, ...]


@dataclass(frozen=True)
class WatertightnessReport:
    """Aggregated watertightness report for all solids."""

    per_solid: Mapping[str, tuple[ShellWatertightness, ...]]

    def failed_shells(self) -> tuple[tuple[str, int], ...]:
        """Return ``(solid_id, shell_index)`` for every failed shell."""
        result: list[tuple[str, int]] = []
        for solid_id, shells in self.per_solid.items():
            for sw in shells:
                if not sw.pass_:
                    result.append((solid_id, sw.shell_index))
        return tuple(result)

    def is_watertight(self) -> bool:
        return len(self.failed_shells()) == 0


def validate_watertightness(
    solids: Sequence[HealedSolid],
) -> WatertightnessReport:
    """Validate watertightness of all shells in all solids."""
    per_solid: dict[str, tuple[ShellWatertightness, ...]] = {}

    for solid in solids:
        shell_results: list[ShellWatertightness] = []
        for shell in solid.shells:
            result = _check_shell(shell.vertices, shell.faces, shell.shell_index)
            shell_results.append(result)
            if not result.pass_:
                _LOG.warning(
                    "watertightness.fail",
                    solid_id=solid.solid_id,
                    shell_index=shell.shell_index,
                    unpaired=len(result.unpaired_edges),
                    same_orient=len(result.same_orientation_edges),
                    degenerate=len(result.degenerate_triangles),
                )
        per_solid[solid.solid_id] = tuple(shell_results)

    return WatertightnessReport(per_solid=per_solid)


def _check_shell(
    vertices: np.ndarray,
    faces: np.ndarray,
    shell_index: int,
) -> ShellWatertightness:
    """Check one shell for watertightness via edge-pairing."""
    # Canonicalize vertices: merge within tolerance.
    inv_tol = 1.0 / VERTEX_MERGE_TOL_MM if VERTEX_MERGE_TOL_MM > 0 else 1.0
    rounded = np.rint(vertices * inv_tol).astype(np.int64)

    # Build unique vertex map.
    unique_map: dict[bytes, int] = {}
    remap = np.empty(vertices.shape[0], dtype=np.int64)
    next_id = 0
    for i in range(vertices.shape[0]):
        key = rounded[i].tobytes()
        if key not in unique_map:
            unique_map[key] = next_id
            next_id += 1
        remap[i] = unique_map[key]

    # Remap faces.
    remapped_faces = remap[faces]

    # Find degenerate triangles (any two vertices same after remap).
    degenerate: list[int] = []
    for tri_idx in range(remapped_faces.shape[0]):
        f = remapped_faces[tri_idx]
        if f[0] == f[1] or f[1] == f[2] or f[0] == f[2]:
            degenerate.append(tri_idx)

    # Build edge map (excluding degenerate triangles).
    degenerate_set = set(degenerate)
    # edge (sorted pair) → list of (tri_idx, is_forward)
    # is_forward = True means edge appears as (v_a, v_b) with v_a < v_b in face order
    edge_data: dict[tuple[int, int], list[tuple[int, bool]]] = defaultdict(list)

    for tri_idx in range(remapped_faces.shape[0]):
        if tri_idx in degenerate_set:
            continue
        f = remapped_faces[tri_idx]
        for k in range(3):
            va = int(f[k])
            vb = int(f[(k + 1) % 3])
            edge_key = (min(va, vb), max(va, vb))
            is_forward = va < vb
            edge_data[edge_key].append((tri_idx, is_forward))

    unpaired: list[tuple[int, int]] = []
    same_orient: list[tuple[int, int]] = []

    for edge_key, entries in edge_data.items():
        if len(entries) != 2:
            unpaired.append(edge_key)
        elif entries[0][1] == entries[1][1]:
            same_orient.append(edge_key)

    pass_ = len(unpaired) == 0 and len(same_orient) == 0 and len(degenerate) == 0

    return ShellWatertightness(
        shell_index=shell_index,
        pass_=pass_,
        unpaired_edges=tuple(unpaired),
        same_orientation_edges=tuple(same_orient),
        degenerate_triangles=tuple(degenerate),
    )
