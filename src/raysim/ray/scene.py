"""Scene loader and Embree BVH builder — Phase A.3.

Stage A consumes geometry as a directory of STL files (one file per material
``group_id``) plus a ``Material`` library and a ``MaterialAssignment[]`` list.
Each STL is loaded with :mod:`trimesh`, registered as one Embree
``TriangleMesh`` (so ``geomID`` == "this material's solid"), and indexed for
the iterative closest-hit traversal in :mod:`raysim.ray.tracer`.

Coincident-face detection (mandatory tie-handling per
``docs/decisions/phase-0.md`` — embreex 4.4 has no filter-callback API):
this module pre-builds a map ``(geom_id, prim_id) → tied_group_id`` so that
when the traversal closest-hit returns one primitive of a tied group, the
others are processed in the same iteration without a second Embree query.

Scope note: Phase A's coincident-face detection is the subset of B1.5 needed
to make the concentric-shell acceptance test pass. The detector hashes a
triangle by its three vertex coordinates (rounded, sorted) — so two triangles
with **identical vertex sets** from different solids are paired. Two
coplanar triangles with the *same plane* but different triangulations
(e.g. a box face touching a panel face split along a different diagonal) are
**not** paired by this detector and will therefore mis-handle as if they
were independent surfaces. B1.5 extends this to full coplanar-region
classification (``contact_only``/``accepted_nested``/``interference_*``)
and the runtime overlap diagnostic; Phase A's acceptance fixtures
(``aluminum_box``, ``solid_sphere``, ``concentric_shell``) all have either
no coincidence or vertex-identical coincidence and are unaffected.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import structlog
import trimesh
from numpy.typing import NDArray

from raysim.proj.schema import Material, MaterialAssignment

_LOG = structlog.get_logger(__name__)


@dataclass(frozen=True)
class SolidEntry:
    """One Embree geometry: a single material's mesh."""

    solid_id: str
    material_group_id: str
    density_g_cm3: float
    geom_id: int  # Embree geomID assigned at scene-build time
    n_triangles: int
    bbox_min_mm: tuple[float, float, float]
    bbox_max_mm: tuple[float, float, float]


@dataclass(frozen=True)
class PreBuiltTiedGroups:
    """Pre-built coincident-face groups from the geometry pipeline (B1.5).

    Replaces the in-line vertex-set detector when the STEP path has richer
    information.  Used exclusively by ``raysim.geom.adapter``.
    """

    tied_group_id_per_geom: tuple[NDArray[np.int32], ...]
    tied_group_members: Mapping[int, tuple[tuple[int, int], ...]]


@dataclass
class BuiltScene:
    """Assembled Embree scene + the metadata the traversal needs.

    Attributes
    ----------
    embree_scene :
        ``embreex.rtcore_scene.EmbreeScene``. Held opaquely.
    solids :
        Per-``geom_id`` solid metadata (material, density, triangle count).
    density_per_geom :
        Float64 array of shape ``(n_geoms,)``; ``density_per_geom[geom_id]``
        is the solid's density in g/cm³.
    solid_id_per_geom :
        Per-``geom_id`` solid identifier, used for stack accumulator keys.
    triangle_normals_per_geom :
        Per-geom float64 ``(n_tri, 3)`` of triangle normal *directions* —
        unit-normalized, outward-pointing per the §B1.3 convention. Used to
        classify entry/exit on tie batches without re-reading Embree's ``Ng``
        (which is not unit-length and may be flipped on tied-group lookups).
    tied_group_id_per_geom :
        Per-geom int32 array; ``tied_group_id_per_geom[geom_id][prim_id]`` is
        ``-1`` if the triangle has no coincident partner, else a non-negative
        group id shared with every coincident triangle in the scene.
    tied_group_members :
        Mapping from group id to a tuple of ``(geom_id, prim_id)`` pairs in
        deterministic order (sorted lex on (geom_id, prim_id)).
    bbox_min_mm, bbox_max_mm, bbox_diag_mm :
        Scene-level AABB and its space diagonal length, in mm.
    """

    embree_scene: object
    solids: tuple[SolidEntry, ...]
    density_per_geom: NDArray[np.float64]
    solid_id_per_geom: tuple[str, ...]
    triangle_normals_per_geom: tuple[NDArray[np.float64], ...]
    tied_group_id_per_geom: tuple[NDArray[np.int32], ...]
    tied_group_members: Mapping[int, tuple[tuple[int, int], ...]]
    bbox_min_mm: tuple[float, float, float]
    bbox_max_mm: tuple[float, float, float]
    bbox_diag_mm: float


# ---------------------------------------------------------------------------
# Scene loading
# ---------------------------------------------------------------------------


def load_scene_from_directory(
    directory: str | Path,
    materials: Sequence[Material],
    assignments: Sequence[MaterialAssignment] | None = None,
    *,
    tied_groups: PreBuiltTiedGroups | None = None,
    process_meshes: bool = True,
) -> BuiltScene:
    """Load a directory of STLs (one file per ``solid_id``) into a scene.

    Convention: every ``*.stl`` file in ``directory``'s top level is one solid
    whose ``solid_id`` is the file stem. ``assignments`` maps each ``solid_id``
    to a library ``material_group_id``; if omitted, ``solid_id`` is treated as
    the material group id directly (so the canonical ``aluminum.stl`` →
    ``"aluminum"`` material).

    Parameters
    ----------
    tied_groups :
        When supplied (from the STEP geometry pipeline), skip the in-line
        vertex-set coincident-face detector and use these pre-built groups.
    process_meshes :
        When ``False``, pass ``process=False`` to ``trimesh.load`` to preserve
        STL face order.  Used by the B1.6 adapter to maintain the
        ``triangle_index_map`` → Embree ``primID`` correspondence.
    """
    directory = Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(f"scene directory not found: {directory}")
    stl_paths = sorted(directory.glob("*.stl"))
    if not stl_paths:
        raise FileNotFoundError(f"no STL files in scene directory: {directory}")
    entries: list[tuple[str, Path]] = [(p.stem, p) for p in stl_paths]
    return load_scene(entries, materials, assignments,
                      tied_groups=tied_groups, process_meshes=process_meshes)


def load_scene(
    solids: Iterable[tuple[str, str | Path]],
    materials: Sequence[Material],
    assignments: Sequence[MaterialAssignment] | None = None,
    *,
    tied_groups: PreBuiltTiedGroups | None = None,
    process_meshes: bool = True,
) -> BuiltScene:
    """Build an Embree scene from an explicit ``[(solid_id, stl_path), ...]``."""
    # Resolve material lookup.
    mat_by_id: dict[str, Material] = {m.group_id: m for m in materials}
    if assignments is None:
        assignment_map: dict[str, str] = {}
    else:
        assignment_map = {a.solid_id: a.material_group_id for a in assignments}

    # Lazy-import embreex so non-ray test paths don't pay for it.
    from embreex.mesh_construction import TriangleMesh
    from embreex.rtcore_scene import EmbreeScene

    embree_scene = EmbreeScene()
    solid_entries: list[SolidEntry] = []
    triangle_normals: list[NDArray[np.float64]] = []
    densities: list[float] = []
    solid_ids: list[str] = []

    # For coincident-face detection across all geoms.
    all_vertices: list[NDArray[np.float64]] = []
    all_faces: list[NDArray[np.int64]] = []

    bbox_min = np.array([np.inf, np.inf, np.inf], dtype=np.float64)
    bbox_max = np.array([-np.inf, -np.inf, -np.inf], dtype=np.float64)

    for geom_id, (solid_id, stl_path) in enumerate(solids):
        path = Path(stl_path)
        if process_meshes:
            mesh = trimesh.load(path, force="mesh")
        else:
            mesh = trimesh.load(path, force="mesh", process=False)
        if not isinstance(mesh, trimesh.Trimesh):  # pragma: no cover - defensive
            raise ValueError(f"{path}: not a triangle mesh")
        verts = np.asarray(mesh.vertices, dtype=np.float64)
        faces = np.asarray(mesh.faces, dtype=np.int64)
        if faces.size == 0:
            raise ValueError(f"{path}: empty mesh")

        material_id = assignment_map.get(solid_id, solid_id)
        if material_id not in mat_by_id:
            raise KeyError(
                f"solid {solid_id!r} → material {material_id!r} not in library "
                f"(known: {sorted(mat_by_id)})"
            )
        material = mat_by_id[material_id]

        # Compute per-triangle normals in float64 for the entry/exit decision.
        # Trimesh.face_normals are unit-normalized and oriented per the source
        # mesh's face winding (CCW from the outside). The healed Stage B
        # pipeline guarantees outward-pointing normals; for Stage A's STL
        # input we trust the source.
        normals = _compute_unit_normals(verts, faces)
        triangle_normals.append(normals)

        # Register the geometry with Embree (float32 vertices is Embree native).
        verts_f32 = verts.astype(np.float32, copy=False)
        TriangleMesh(embree_scene, verts_f32[faces])

        densities.append(float(material.density_g_cm3))
        solid_ids.append(solid_id)
        bb_min = verts.min(axis=0)
        bb_max = verts.max(axis=0)
        bbox_min = np.minimum(bbox_min, bb_min)
        bbox_max = np.maximum(bbox_max, bb_max)

        solid_entries.append(
            SolidEntry(
                solid_id=solid_id,
                material_group_id=material_id,
                density_g_cm3=float(material.density_g_cm3),
                geom_id=geom_id,
                n_triangles=int(faces.shape[0]),
                bbox_min_mm=(float(bb_min[0]), float(bb_min[1]), float(bb_min[2])),
                bbox_max_mm=(float(bb_max[0]), float(bb_max[1]), float(bb_max[2])),
            )
        )
        all_vertices.append(verts)
        all_faces.append(faces)
        _LOG.debug(
            "scene.geom_loaded",
            geom_id=geom_id,
            solid_id=solid_id,
            material=material_id,
            density_g_cm3=material.density_g_cm3,
            n_triangles=int(faces.shape[0]),
        )

    bbox_diag = float(np.linalg.norm(bbox_max - bbox_min))

    # Coincident-face groups: use pre-built groups from the STEP pipeline
    # when supplied, otherwise detect via vertex-set hashing.
    if tied_groups is not None:
        tied_group_id_per_geom_result: list[NDArray[np.int32]] = list(
            tied_groups.tied_group_id_per_geom
        )
        tied_group_members_result: dict[int, tuple[tuple[int, int], ...]] = dict(
            tied_groups.tied_group_members
        )
        _LOG.info(
            "scene.prebuilt_tied_groups",
            n_groups=len(tied_group_members_result),
        )
    else:
        tol_mm = max(1e-9, 1e-6 * bbox_diag)
        tied_group_id_per_geom_result, tied_group_members_result = _build_tied_groups(
            all_vertices, all_faces, tol_mm
        )

    embree_scene.commit() if hasattr(embree_scene, "commit") else None

    return BuiltScene(
        embree_scene=embree_scene,
        solids=tuple(solid_entries),
        density_per_geom=np.asarray(densities, dtype=np.float64),
        solid_id_per_geom=tuple(solid_ids),
        triangle_normals_per_geom=tuple(triangle_normals),
        tied_group_id_per_geom=tuple(tied_group_id_per_geom_result),
        tied_group_members=tied_group_members_result,
        bbox_min_mm=(float(bbox_min[0]), float(bbox_min[1]), float(bbox_min[2])),
        bbox_max_mm=(float(bbox_max[0]), float(bbox_max[1]), float(bbox_max[2])),
        bbox_diag_mm=bbox_diag,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_unit_normals(
    verts: NDArray[np.float64], faces: NDArray[np.int64]
) -> NDArray[np.float64]:
    v0 = verts[faces[:, 0]]
    v1 = verts[faces[:, 1]]
    v2 = verts[faces[:, 2]]
    n = np.cross(v1 - v0, v2 - v0)
    norm = np.linalg.norm(n, axis=1, keepdims=True)
    norm = np.where(norm == 0, 1.0, norm)
    return (n / norm).astype(np.float64, copy=False)


def _build_tied_groups(
    verts_per_geom: Sequence[NDArray[np.float64]],
    faces_per_geom: Sequence[NDArray[np.int64]],
    tol_mm: float,
) -> tuple[list[NDArray[np.int32]], dict[int, tuple[tuple[int, int], ...]]]:
    """Group triangles whose vertex sets coincide within tolerance.

    Identification: hash a triangle by the byte representation of its three
    vertices, each rounded to ``round(coord / tol_mm) * tol_mm`` and sorted
    lexicographically. Triangles from different geoms with identical hashes
    (i.e. a coincident facet) become a tied group.

    Group id is ``-1`` for triangles with no partner (the common case).
    """
    # Bucket triangles by hash → list of (geom_id, prim_id).
    bucket: dict[bytes, list[tuple[int, int]]] = {}
    inv_tol = 1.0 / tol_mm if tol_mm > 0 else 1.0

    n_geoms = len(verts_per_geom)
    if n_geoms != len(faces_per_geom):
        raise ValueError("mismatched verts/faces lists")

    for geom_id in range(n_geoms):
        verts = verts_per_geom[geom_id]
        faces = faces_per_geom[geom_id]
        # Vertex coordinates rounded to grid (avoid -0.0 vs +0.0 hash drift).
        v_round = np.rint(verts * inv_tol).astype(np.int64)
        for prim_id in range(faces.shape[0]):
            tri = v_round[faces[prim_id]]  # (3, 3) ints
            # Sort the three vertices lexicographically, then hash.
            order = np.lexsort(tri.T[::-1])
            sorted_tri = tri[order]
            key = sorted_tri.tobytes()
            bucket.setdefault(key, []).append((geom_id, prim_id))

    # Allocate per-geom -1 arrays.
    tied_group_id_per_geom: list[NDArray[np.int32]] = [
        np.full(faces_per_geom[g].shape[0], -1, dtype=np.int32) for g in range(n_geoms)
    ]
    members: dict[int, tuple[tuple[int, int], ...]] = {}

    next_group = 0
    # Sort buckets by representative (geom_id, prim_id) for stable group ids
    # across runs — important for byte-identical run.json reproducibility.
    multi = sorted(
        ((sorted(v), v) for v in bucket.values() if len(v) > 1),
        key=lambda pair: pair[0][0],
    )
    for sorted_members, _ in multi:
        gid = next_group
        next_group += 1
        members[gid] = tuple(sorted_members)
        for geom_id, prim_id in sorted_members:
            tied_group_id_per_geom[geom_id][prim_id] = gid

    if next_group:
        _LOG.info(
            "scene.tied_groups_built",
            n_groups=next_group,
            n_tri_total=sum(int(f.shape[0]) for f in faces_per_geom),
            tol_mm=tol_mm,
        )

    return tied_group_id_per_geom, members
