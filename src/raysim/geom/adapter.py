"""STEP→Stage-A adapter — Phase B1.6.

Exports healed solids as STL via an in-house binary writer (deterministic),
then hands off to ``raysim.ray.scene.load_scene_from_directory`` with
STEP-derived tied groups passed through ``PreBuiltTiedGroups``.
"""

from __future__ import annotations

import struct
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import structlog
from numpy.typing import NDArray

from raysim.geom.healing import HealedSolid
from raysim.geom.overlap import OverlapReport, TiedTrianglePair
from raysim.geom.pipeline import ValidatedAssembly, ValidationOverrides, build_assembly_from_step
from raysim.geom.watertightness import WatertightnessReport
from raysim.proj.schema import Material, MaterialAssignment
from raysim.ray.scene import BuiltScene, PreBuiltTiedGroups, load_scene_from_directory

_LOG = structlog.get_logger(__name__)


class GeomValidationError(RuntimeError):
    """Raised when watertightness or interference gates trip without override."""


@dataclass(frozen=True)
class ExportedSolid:
    """One STL written by the adapter."""

    solid_id: str
    path: Path
    triangle_index_map: NDArray[np.int64]  # tessellation_idx -> export_idx


def build_scene_from_step(
    step_path: str | Path,
    *,
    materials: Sequence[Material],
    assignments: Sequence[MaterialAssignment] | None = None,
    linear_mm: float = 0.1,
    angular_rad: float = 0.5,
    accept_warnings: bool = False,
    accept_interference_fail: bool = False,
    accept_watertightness_failures: bool = False,
) -> tuple[BuiltScene, ValidatedAssembly]:
    """Full STEP→BuiltScene pipeline with validation gates."""
    assembly = build_assembly_from_step(
        step_path, linear_mm=linear_mm, angular_rad=angular_rad,
    )

    # Apply validation gates.
    _gate_watertightness(assembly.watertightness, accept_watertightness_failures)
    _gate_overlaps(assembly.overlaps, accept_warnings, accept_interference_fail)

    overrides = ValidationOverrides(
        accept_warnings=accept_warnings,
        accept_interference_fail=accept_interference_fail,
        accept_watertightness_failures=accept_watertightness_failures,
    )
    assembly = replace(assembly, overrides_used=overrides)

    # Export STLs and build the scene.
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        exported = export_assembly_to_stl(assembly, tmp_path)

        # Build tied groups from STEP-derived pairs.
        tied = _build_tied_groups(
            assembly.overlaps.all_tied_triangle_pairs(),
            exported,
            assembly.solids,
        )

        scene = load_scene_from_directory(
            tmp_path,
            materials,
            assignments,
            tied_groups=tied,
            process_meshes=False,
        )

    return scene, assembly


def export_assembly_to_stl(
    assembly: ValidatedAssembly,
    out_dir: Path,
) -> tuple[ExportedSolid, ...]:
    """Write one deterministic binary STL per healed solid."""
    out_dir.mkdir(parents=True, exist_ok=True)
    result: list[ExportedSolid] = []

    for solid in assembly.solids:
        verts, faces, normals = _flatten_solid(solid)
        if faces.shape[0] == 0:
            continue

        # Lex-sort triangles for deterministic output.
        sort_keys, index_map = _lex_sort_triangles(verts, faces)

        sorted_faces = faces[sort_keys]
        sorted_normals = normals[sort_keys]

        path = out_dir / f"{solid.solid_id}.stl"
        _write_binary_stl(path, verts, sorted_faces, sorted_normals)

        result.append(ExportedSolid(
            solid_id=solid.solid_id,
            path=path,
            triangle_index_map=index_map,
        ))

    return tuple(result)


# ---------------------------------------------------------------------------
# Validation gates
# ---------------------------------------------------------------------------


def _gate_watertightness(
    report: WatertightnessReport,
    accept: bool,
) -> None:
    failed = report.failed_shells()
    if failed and not accept:
        shells_str = ", ".join(f"{sid}:shell_{idx}" for sid, idx in failed)
        raise GeomValidationError(
            f"Non-watertight shells detected: {shells_str}. "
            "Pass accept_watertightness_failures=True to override."
        )


def _gate_overlaps(
    report: OverlapReport,
    accept_warnings: bool,
    accept_interference_fail: bool,
) -> None:
    fails = report.failed()
    if fails and not (accept_warnings and accept_interference_fail):
        pairs_str = ", ".join(f"{p.solid_a}/{p.solid_b}" for p in fails)
        raise GeomValidationError(
            f"Interference failures detected: {pairs_str}. "
            "Pass accept_warnings=True AND accept_interference_fail=True to override."
        )

    warnings = report.warnings()
    mismatched = report.mismatched_contacts
    bool_failures = report.boolean_failures

    if (warnings or mismatched or bool_failures) and not accept_warnings:
        parts: list[str] = []
        if warnings:
            parts.append(f"{len(warnings)} interference warnings")
        if mismatched:
            parts.append(f"{len(mismatched)} mismatched contact regions")
        if bool_failures:
            parts.append(f"{len(bool_failures)} boolean failures")
        raise GeomValidationError(
            f"Overlap warnings: {', '.join(parts)}. "
            "Pass accept_warnings=True to override."
        )


# ---------------------------------------------------------------------------
# STL export helpers
# ---------------------------------------------------------------------------


def _flatten_solid(
    solid: HealedSolid,
) -> tuple[NDArray[np.float64], NDArray[np.int64], NDArray[np.float64]]:
    """Combine all shells into flat vertex/face/normal arrays."""
    all_verts: list[NDArray[np.float64]] = []
    all_faces: list[NDArray[np.int64]] = []
    all_normals: list[NDArray[np.float64]] = []
    vert_offset = 0

    for shell in solid.shells:
        all_verts.append(shell.vertices)
        all_faces.append(shell.faces + vert_offset)
        all_normals.append(shell.triangle_normals)
        vert_offset += shell.vertices.shape[0]

    if not all_verts:
        return (
            np.empty((0, 3), dtype=np.float64),
            np.empty((0, 3), dtype=np.int64),
            np.empty((0, 3), dtype=np.float64),
        )

    return np.vstack(all_verts), np.vstack(all_faces), np.vstack(all_normals)


def _lex_sort_triangles(
    verts: NDArray[np.float64],
    faces: NDArray[np.int64],
) -> tuple[NDArray[np.int64], NDArray[np.int64]]:
    """Lex-sort triangles by rounded vertex coordinates.

    Returns ``(sort_order, index_map)`` where
    ``index_map[original_idx] = sorted_idx``.
    """
    n_tri = faces.shape[0]
    # Round vertices to 6 decimals (micron precision).
    rounded = np.round(verts, decimals=6)

    # Build sort keys: per-triangle, sort the 3 vertices lex, then sort
    # triangles by their sorted vertex tuples.
    keys: list[tuple[tuple[float, ...], ...]] = []
    for i in range(n_tri):
        tri_verts = rounded[faces[i]]
        sorted_verts = sorted(tuple(v) for v in tri_verts)
        keys.append(tuple(sorted_verts))

    sort_order = np.array(sorted(range(n_tri), key=lambda i: keys[i]), dtype=np.int64)

    # index_map[original_flat_idx] = export_idx
    index_map = np.empty(n_tri, dtype=np.int64)
    for export_idx, orig_idx in enumerate(sort_order):
        index_map[orig_idx] = export_idx

    return sort_order, index_map


def _write_binary_stl(
    path: Path,
    verts: NDArray[np.float64],
    faces: NDArray[np.int64],
    normals: NDArray[np.float64],
) -> None:
    """Write a deterministic binary STL file."""
    n_tri = faces.shape[0]
    verts_f32 = verts.astype(np.float32)
    normals_f32 = normals.astype(np.float32)

    with open(path, "wb") as f:
        # 80-byte header (zeroed).
        f.write(b"\x00" * 80)
        # Number of triangles (uint32 little-endian).
        f.write(struct.pack("<I", n_tri))
        for i in range(n_tri):
            # Normal (3 × float32).
            f.write(struct.pack("<3f", *normals_f32[i]))
            # 3 vertices (9 × float32).
            for vi in range(3):
                f.write(struct.pack("<3f", *verts_f32[faces[i, vi]]))
            # Attribute byte count (uint16 = 0).
            f.write(struct.pack("<H", 0))


# ---------------------------------------------------------------------------
# Tied-group translation
# ---------------------------------------------------------------------------


def _build_tied_groups(
    tied_pairs: tuple[TiedTrianglePair, ...],
    exported: tuple[ExportedSolid, ...],
    solids: tuple[HealedSolid, ...],
) -> PreBuiltTiedGroups | None:
    """Translate B1.5's ``TiedTrianglePair`` through export index maps
    into ``PreBuiltTiedGroups`` for the scene loader."""
    if not tied_pairs:
        # Return an empty PreBuiltTiedGroups so the scene loader
        # skips the Stage A vertex-set detector entirely.
        n_geoms = len(exported)
        empty_per_geom = []
        for solid in solids:
            total = sum(shell.faces.shape[0] for shell in solid.shells)
            empty_per_geom.append(np.full(total, -1, dtype=np.int32))
        return PreBuiltTiedGroups(
            tied_group_id_per_geom=tuple(empty_per_geom),
            tied_group_members={},
        )

    # Build solid_id → (geom_id_in_export_order, ExportedSolid) mapping.
    solid_to_geom: dict[str, int] = {}
    solid_to_export: dict[str, ExportedSolid] = {}
    for geom_id, es in enumerate(exported):
        solid_to_geom[es.solid_id] = geom_id
        solid_to_export[es.solid_id] = es

    n_geoms = len(exported)

    # Count triangles per geom for array allocation.
    n_tris_per_geom: list[int] = []
    for solid in solids:
        total = sum(shell.faces.shape[0] for shell in solid.shells)
        n_tris_per_geom.append(total)

    tied_group_id_per_geom: list[NDArray[np.int32]] = [
        np.full(n_tris_per_geom[i], -1, dtype=np.int32) for i in range(n_geoms)
    ]
    members: dict[int, tuple[tuple[int, int], ...]] = {}

    for gid, pair in enumerate(tied_pairs):
        geom_a = solid_to_geom.get(pair.solid_a)
        geom_b = solid_to_geom.get(pair.solid_b)
        export_a = solid_to_export.get(pair.solid_a)
        export_b = solid_to_export.get(pair.solid_b)

        if geom_a is None or geom_b is None or export_a is None or export_b is None:
            continue

        # Translate tessellation flat index to export (Embree) prim_id.
        prim_a = int(export_a.triangle_index_map[pair.prim_a])
        prim_b = int(export_b.triangle_index_map[pair.prim_b])

        tied_group_id_per_geom[geom_a][prim_a] = gid
        tied_group_id_per_geom[geom_b][prim_b] = gid

        pair_members = sorted([(geom_a, prim_a), (geom_b, prim_b)])
        members[gid] = tuple(pair_members)

    return PreBuiltTiedGroups(
        tied_group_id_per_geom=tuple(tied_group_id_per_geom),
        tied_group_members=members,
    )
