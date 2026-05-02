"""Overlap / interference diagnostic — Phase B1.5.

Face-level coplanar classification + triangle-level vertex-match tie pairing
+ four-way solid-pair status.  The tied-group payload flowing into the engine
is size-2 pairs of vertex-matching triangles, not entire contact faces.

Scope decision for B1: handles only the topology-shared contact case — two
solids whose contact faces share the underlying ``TopoDS_Face`` in the STEP,
producing identical triangulations.  Mismatched-tessellation contacts are
detected and reported as ``MismatchedContactRegion`` warnings; mesh-Boolean
re-triangulation is deferred to B1.5b / B5.x.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import structlog
from numpy.typing import NDArray

from raysim.geom.healing import HealedSolid

_LOG = structlog.get_logger(__name__)

# Module-level tolerance constants.
COPLANAR_NORMAL_TOL_RAD: float = 1e-6
COPLANAR_PLANE_TOL_REL: float = 1e-6
VERTEX_MATCH_TOL_REL: float = 1e-6
COVERAGE_EPSILON: float = 1e-3
ZERO_VOLUME_REL: float = 1e-9
NESTED_VOLUME_REL: float = 1e-6


class OverlapStatus(StrEnum):
    CONTACT_ONLY = "contact_only"
    ACCEPTED_NESTED = "accepted_nested"
    INTERFERENCE_WARNING = "interference_warning"
    INTERFERENCE_FAIL = "interference_fail"


@dataclass(frozen=True)
class TiedTrianglePair:
    """One size-2 tied group: a triangle in solid_a coincident with a triangle
    in solid_b on a shared plane."""

    solid_a: str
    prim_a: int  # per-solid flat triangle index
    solid_b: str
    prim_b: int  # per-solid flat triangle index


@dataclass(frozen=True)
class MismatchedContactRegion:
    """Coplanar contact whose vertex-match coverage falls below threshold."""

    solid_a: str
    solid_b: str
    face_a_index: int
    face_b_index: int
    shared_area_mm2: float
    matched_area_fraction: float


@dataclass(frozen=True)
class OverlapPair:
    """Classification of the overlap between two solids."""

    solid_a: str
    solid_b: str
    status: OverlapStatus
    intersection_volume_mm3: float
    bias_estimate_g_per_cm2: float
    tied_triangle_pairs: tuple[TiedTrianglePair, ...]


@dataclass(frozen=True)
class BooleanFailure:
    """Recorded when an OCCT boolean operation fails."""

    solid_a: str
    solid_b: str
    operation: str  # "common_face" | "common_volume"
    occt_message: str


@dataclass(frozen=True)
class ContactReport:
    """Fast contact extraction result — tied pairs + mismatched contacts.

    Produced by ``extract_contacts()`` (no OCCT volume classification).
    The ray engine needs tied pairs (ARCHI §11) and mismatched contacts
    must still gate/warn (ARCHI §9b).
    """

    tied_pairs: tuple[TiedTrianglePair, ...]
    mismatched_contacts: tuple[MismatchedContactRegion, ...]


@dataclass(frozen=True)
class OverlapReport:
    """Full overlap diagnostic for an assembly."""

    pairs: tuple[OverlapPair, ...]
    mismatched_contacts: tuple[MismatchedContactRegion, ...]
    boolean_failures: tuple[BooleanFailure, ...]

    def failed(self) -> tuple[OverlapPair, ...]:
        return tuple(p for p in self.pairs if p.status == OverlapStatus.INTERFERENCE_FAIL)

    def warnings(self) -> tuple[OverlapPair, ...]:
        return tuple(p for p in self.pairs if p.status == OverlapStatus.INTERFERENCE_WARNING)

    def all_tied_triangle_pairs(self) -> tuple[TiedTrianglePair, ...]:
        result: list[TiedTrianglePair] = []
        for p in self.pairs:
            result.extend(p.tied_triangle_pairs)
        return tuple(result)


def extract_contacts(
    solids: Sequence[HealedSolid],
    *,
    coplanar_normal_tol_rad: float = COPLANAR_NORMAL_TOL_RAD,
    coplanar_plane_tol_relative: float = COPLANAR_PLANE_TOL_REL,
    vertex_match_tol_relative: float = VERTEX_MATCH_TOL_REL,
    coverage_epsilon: float = COVERAGE_EPSILON,
) -> ContactReport:
    """Fast contact extraction: AABB filter + triangle-match tied pairing.

    No OCCT volume classification.  Returns tied pairs needed by the ray
    engine and mismatched-contact warnings for the pipeline gate.
    """
    if len(solids) < 2:
        return ContactReport(tied_pairs=(), mismatched_contacts=())

    bbox_diag = _compute_assembly_bbox_diag(solids)
    plane_tol = coplanar_plane_tol_relative * bbox_diag
    vtx_tol = vertex_match_tol_relative * bbox_diag

    all_tied: list[TiedTrianglePair] = []
    all_mismatched: list[MismatchedContactRegion] = []

    sorted_solids = sorted(solids, key=lambda s: s.solid_id)
    candidate_pairs = _spatial_hash_pairs(sorted_solids)

    _LOG.info("overlap.contact_candidates", n_total=len(sorted_solids), n_pairs=len(candidate_pairs))

    for sa, sb in candidate_pairs:
        if not _aabb_overlap(sa, sb):
            continue

        tied_pairs, mcr_list = _detect_coplanar_contacts(
            sa, sb,
            coplanar_normal_tol_rad=coplanar_normal_tol_rad,
            plane_tol_mm=plane_tol,
            vtx_tol_mm=vtx_tol,
            coverage_epsilon=coverage_epsilon,
        )
        all_tied.extend(tied_pairs)
        all_mismatched.extend(mcr_list)

    _LOG.info(
        "overlap.contacts_extracted",
        n_tied=len(all_tied),
        n_mismatched=len(all_mismatched),
    )
    return ContactReport(
        tied_pairs=tuple(all_tied),
        mismatched_contacts=tuple(all_mismatched),
    )


def diagnose_overlaps(
    solids: Sequence[HealedSolid],
    *,
    shapes: Mapping[str, object] | None = None,
    small_volume_threshold_mm3: float = 1.0,
    small_relative_volume: float = 1e-3,
    coplanar_normal_tol_rad: float = COPLANAR_NORMAL_TOL_RAD,
    coplanar_plane_tol_relative: float = COPLANAR_PLANE_TOL_REL,
    vertex_match_tol_relative: float = VERTEX_MATCH_TOL_REL,
    coverage_epsilon: float = COVERAGE_EPSILON,
) -> OverlapReport:
    """Run the full overlap diagnostic on all solid pairs.

    Parameters
    ----------
    shapes :
        Optional mapping ``{solid_id: TopoDS_Solid}`` for volume-based
        classification.  When omitted, only triangle-level vertex-match
        pairing and coplanar coverage are evaluated; volume-based
        classification defaults to ``contact_only`` for AABB-overlapping pairs.
    """
    if len(solids) < 2:
        return OverlapReport(pairs=(), mismatched_contacts=(), boolean_failures=())

    bbox_diag = _compute_assembly_bbox_diag(solids)
    plane_tol = coplanar_plane_tol_relative * bbox_diag
    vtx_tol = vertex_match_tol_relative * bbox_diag

    pairs: list[OverlapPair] = []
    mismatched: list[MismatchedContactRegion] = []
    bool_failures: list[BooleanFailure] = []

    sorted_solids = sorted(solids, key=lambda s: s.solid_id)
    candidate_pairs = _spatial_hash_pairs(sorted_solids)

    _LOG.info("overlap.diagnose_candidates", n_total=len(sorted_solids), n_pairs=len(candidate_pairs))

    for sa, sb in candidate_pairs:
        if not _aabb_overlap(sa, sb):
            continue

        tied_pairs, mcr_list = _detect_coplanar_contacts(
            sa, sb,
            coplanar_normal_tol_rad=coplanar_normal_tol_rad,
            plane_tol_mm=plane_tol,
            vtx_tol_mm=vtx_tol,
            coverage_epsilon=coverage_epsilon,
        )
        mismatched.extend(mcr_list)

        # Early-exit: if contacts fully explain the AABB overlap
        # (tied pairs exist, no mismatches) and the AABBs don't
        # overlap with negative margin, skip the expensive OCCT
        # volume classification.
        if tied_pairs and not mcr_list and not _aabb_overlap_margin(sa, sb, margin_mm=-0.01):
            pairs.append(OverlapPair(
                solid_a=sa.solid_id,
                solid_b=sb.solid_id,
                status=OverlapStatus.CONTACT_ONLY,
                intersection_volume_mm3=0.0,
                bias_estimate_g_per_cm2=0.0,
                tied_triangle_pairs=tuple(tied_pairs),
            ))
            continue

        # Volume classification.
        vol_result = _classify_pair(
            sa, sb,
            shapes=shapes,
            small_volume_threshold_mm3=small_volume_threshold_mm3,
            small_relative_volume=small_relative_volume,
            bool_failures_out=bool_failures,
        )

        if vol_result is not None:
            status, int_vol, bias = vol_result
            pairs.append(OverlapPair(
                solid_a=sa.solid_id,
                solid_b=sb.solid_id,
                status=status,
                intersection_volume_mm3=int_vol,
                bias_estimate_g_per_cm2=bias,
                tied_triangle_pairs=tuple(tied_pairs),
            ))

    _LOG.info(
        "overlap.diagnosed",
        n_pairs=len(pairs),
        n_mismatched=len(mismatched),
        n_bool_failures=len(bool_failures),
    )
    return OverlapReport(
        pairs=tuple(pairs),
        mismatched_contacts=tuple(mismatched),
        boolean_failures=tuple(bool_failures),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _compute_assembly_bbox_diag(solids: Sequence[HealedSolid]) -> float:
    all_mins = np.array([s.bbox_min_mm for s in solids])
    all_maxs = np.array([s.bbox_max_mm for s in solids])
    bbox_min = all_mins.min(axis=0)
    bbox_max = all_maxs.max(axis=0)
    return float(np.linalg.norm(bbox_max - bbox_min))


def _aabb_overlap(a: HealedSolid, b: HealedSolid) -> bool:
    for i in range(3):
        if a.bbox_max_mm[i] < b.bbox_min_mm[i] or b.bbox_max_mm[i] < a.bbox_min_mm[i]:
            return False
    return True


def _aabb_overlap_margin(a: HealedSolid, b: HealedSolid, *, margin_mm: float) -> bool:
    """AABB overlap test with a margin (negative = shrink, positive = expand)."""
    for i in range(3):
        if (a.bbox_max_mm[i] + margin_mm) < (b.bbox_min_mm[i] - margin_mm):
            return False
        if (b.bbox_max_mm[i] + margin_mm) < (a.bbox_min_mm[i] - margin_mm):
            return False
    return True


def _spatial_hash_pairs(
    solids: Sequence[HealedSolid],
) -> list[tuple[HealedSolid, HealedSolid]]:
    """Return candidate pairs using a grid-based spatial hash.

    Cell size = ``2 × median(solid_bbox_diag)``.  Only pairs sharing at
    least one grid cell are returned, with canonical ordering
    (``solid_a.solid_id < solid_b.solid_id``) for deduplication.
    """
    if len(solids) < 2:
        return []

    diags = [
        float(np.linalg.norm(
            np.array(s.bbox_max_mm) - np.array(s.bbox_min_mm),
        ))
        for s in solids
    ]
    cell_size = float(np.median(diags)) * 2.0
    if cell_size < 1e-9:
        cell_size = 1.0

    inv_cell = 1.0 / cell_size

    max_cells_per_solid = 512
    grid: dict[tuple[int, int, int], list[int]] = defaultdict(list)
    oversized: list[int] = []

    for idx, s in enumerate(solids):
        lo = tuple(int(np.floor(v * inv_cell)) for v in s.bbox_min_mm)
        hi = tuple(int(np.floor(v * inv_cell)) for v in s.bbox_max_mm)
        n_cells = (hi[0] - lo[0] + 1) * (hi[1] - lo[1] + 1) * (hi[2] - lo[2] + 1)
        if n_cells > max_cells_per_solid:
            oversized.append(idx)
            continue
        for ix in range(lo[0], hi[0] + 1):
            for iy in range(lo[1], hi[1] + 1):
                for iz in range(lo[2], hi[2] + 1):
                    grid[(ix, iy, iz)].append(idx)

    seen: set[tuple[str, str]] = set()
    result: list[tuple[HealedSolid, HealedSolid]] = []

    def _add_pair(a: HealedSolid, b: HealedSolid) -> None:
        key = (a.solid_id, b.solid_id) if a.solid_id < b.solid_id else (b.solid_id, a.solid_id)
        if key not in seen:
            seen.add(key)
            result.append((a, b) if a.solid_id < b.solid_id else (b, a))

    for cell_members in grid.values():
        for ai in range(len(cell_members)):
            for bi in range(ai + 1, len(cell_members)):
                _add_pair(solids[cell_members[ai]], solids[cell_members[bi]])

    for oi in oversized:
        for idx in range(len(solids)):
            if idx != oi:
                _add_pair(solids[oi], solids[idx])

    return result


def _get_flat_arrays(
    solid: HealedSolid,
) -> tuple[NDArray[np.float64], NDArray[np.int64], NDArray[np.float64]]:
    """Get combined vertices, faces, and normals for all shells."""
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


def _detect_coplanar_contacts(
    sa: HealedSolid,
    sb: HealedSolid,
    *,
    coplanar_normal_tol_rad: float,
    plane_tol_mm: float,
    vtx_tol_mm: float,
    coverage_epsilon: float,
) -> tuple[list[TiedTrianglePair], list[MismatchedContactRegion]]:
    """Detect coplanar triangle pairs between two solids via vertex-set hash."""
    verts_a, faces_a, normals_a = _get_flat_arrays(sa)
    verts_b, faces_b, normals_b = _get_flat_arrays(sb)

    if faces_a.shape[0] == 0 or faces_b.shape[0] == 0:
        return [], []

    inv_tol = 1.0 / vtx_tol_mm if vtx_tol_mm > 0 else 1.0

    # Build hash buckets for B's triangles by their vertex sets.
    b_hash: dict[bytes, list[int]] = defaultdict(list)
    for tri_b in range(faces_b.shape[0]):
        key = _vertex_set_hash(verts_b, faces_b, tri_b, inv_tol)
        b_hash[key].append(tri_b)

    tied_pairs: list[TiedTrianglePair] = []
    matched_a: set[int] = set()
    matched_b: set[int] = set()

    for tri_a in range(faces_a.shape[0]):
        key = _vertex_set_hash(verts_a, faces_a, tri_a, inv_tol)
        candidates = b_hash.get(key, [])
        for tri_b in candidates:
            if tri_b in matched_b:
                continue
            dot = float(np.dot(normals_a[tri_a], normals_b[tri_b]))
            if dot > -1.0 + coplanar_normal_tol_rad:
                _LOG.debug(
                    "overlap.hash_match_not_antiparallel",
                    solid_a=sa.solid_id, tri_a=tri_a,
                    solid_b=sb.solid_id, tri_b=tri_b,
                    dot=dot,
                )
                continue
            tied_pairs.append(TiedTrianglePair(
                solid_a=sa.solid_id,
                prim_a=tri_a,
                solid_b=sb.solid_id,
                prim_b=tri_b,
            ))
            matched_a.add(tri_a)
            matched_b.add(tri_b)
            break

    # Coverage check for coplanar regions.
    mismatched = _check_coverage(
        sa, sb,
        verts_a, faces_a, normals_a,
        verts_b, faces_b, normals_b,
        matched_a,
        coplanar_normal_tol_rad=coplanar_normal_tol_rad,
        plane_tol_mm=plane_tol_mm,
        coverage_epsilon=coverage_epsilon,
    )

    return tied_pairs, mismatched


def _vertex_set_hash(
    verts: NDArray[np.float64],
    faces: NDArray[np.int64],
    tri_idx: int,
    inv_tol: float,
) -> bytes:
    """Hash a triangle by its three vertex coordinates (rounded, sorted lex)."""
    tri_verts = verts[faces[tri_idx]]
    rounded = np.rint(tri_verts * inv_tol).astype(np.int64)
    order = np.lexsort(rounded.T[::-1])
    return bytes(rounded[order].tobytes())


def _triangle_area_3d(
    verts: NDArray[np.float64],
    faces: NDArray[np.int64],
    tri_idx: int,
) -> float:
    v0 = verts[faces[tri_idx, 0]]
    v1 = verts[faces[tri_idx, 1]]
    v2 = verts[faces[tri_idx, 2]]
    return float(0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0)))


def _check_coverage(
    sa: HealedSolid,
    sb: HealedSolid,
    verts_a: NDArray[np.float64],
    faces_a: NDArray[np.int64],
    normals_a: NDArray[np.float64],
    verts_b: NDArray[np.float64],
    faces_b: NDArray[np.int64],
    normals_b: NDArray[np.float64],
    matched_a: set[int],
    *,
    coplanar_normal_tol_rad: float,
    plane_tol_mm: float,
    coverage_epsilon: float,
) -> list[MismatchedContactRegion]:
    """Check if coplanar regions have adequate vertex-match coverage."""
    coplanar_a_tris: set[int] = set()

    for tri_a in range(faces_a.shape[0]):
        centroid_a = verts_a[faces_a[tri_a]].mean(axis=0)
        normal_a = normals_a[tri_a]
        for tri_b in range(faces_b.shape[0]):
            normal_b = normals_b[tri_b]
            dot_n = abs(float(np.dot(normal_a, normal_b)))
            if dot_n < 1.0 - coplanar_normal_tol_rad:
                continue
            centroid_b = verts_b[faces_b[tri_b]].mean(axis=0)
            dist = abs(float(np.dot(normal_a, centroid_b - centroid_a)))
            if dist > plane_tol_mm:
                continue
            coplanar_a_tris.add(tri_a)
            break

    if not coplanar_a_tris:
        return []

    total_area = sum(
        _triangle_area_3d(verts_a, faces_a, t) for t in coplanar_a_tris
    )
    matched_area = sum(
        _triangle_area_3d(verts_a, faces_a, t) for t in coplanar_a_tris if t in matched_a
    )

    if total_area < 1e-12:
        return []

    fraction = matched_area / total_area
    if fraction < 1.0 - coverage_epsilon:
        _LOG.warning(
            "overlap.mismatched_contact",
            solid_a=sa.solid_id,
            solid_b=sb.solid_id,
            shared_area_mm2=total_area,
            matched_fraction=fraction,
        )
        return [MismatchedContactRegion(
            solid_a=sa.solid_id,
            solid_b=sb.solid_id,
            face_a_index=0,
            face_b_index=0,
            shared_area_mm2=total_area,
            matched_area_fraction=fraction,
        )]

    return []


def _classify_pair(
    sa: HealedSolid,
    sb: HealedSolid,
    *,
    shapes: Mapping[str, object] | None,
    small_volume_threshold_mm3: float,
    small_relative_volume: float,
    bool_failures_out: list[BooleanFailure],
) -> tuple[OverlapStatus, float, float] | None:
    """Classify a solid pair by intersection volume.

    Returns ``None`` when the boolean fails (recorded in
    ``bool_failures_out``) — the caller must not create an
    ``OverlapPair`` for undetermined pairs.
    """
    if shapes is None:
        return (OverlapStatus.CONTACT_ONLY, 0.0, 0.0)

    shape_a = shapes.get(sa.solid_id)
    shape_b = shapes.get(sb.solid_id)
    if shape_a is None or shape_b is None:
        return (OverlapStatus.CONTACT_ONLY, 0.0, 0.0)

    try:
        from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Common
        from OCC.Core.BRepGProp import brepgprop
        from OCC.Core.GProp import GProp_GProps

        common = BRepAlgoAPI_Common(shape_a, shape_b)
        if not common.IsDone():
            bool_failures_out.append(BooleanFailure(
                solid_a=sa.solid_id,
                solid_b=sb.solid_id,
                operation="common_volume",
                occt_message="BRepAlgoAPI_Common not done",
            ))
            return None

        common_shape = common.Shape()
        props = GProp_GProps()
        brepgprop.VolumeProperties(common_shape, props)
        int_vol = abs(props.Mass())

        vol_a = _shape_volume(shape_a)
        vol_b = _shape_volume(shape_b)
        min_vol = min(vol_a, vol_b) if vol_a > 0 and vol_b > 0 else 1.0

        avg_density = 5.0
        bias = (int_vol ** (1.0 / 3.0)) * 0.1 * avg_density if int_vol > 0 else 0.0

        if int_vol < ZERO_VOLUME_REL * min_vol:
            return (OverlapStatus.CONTACT_ONLY, int_vol, bias)

        rel = int_vol / min_vol if min_vol > 0 else 0.0
        if abs(rel - 1.0) < NESTED_VOLUME_REL:
            return (OverlapStatus.ACCEPTED_NESTED, int_vol, bias)

        if int_vol < small_volume_threshold_mm3 and rel < small_relative_volume:
            return (OverlapStatus.INTERFERENCE_WARNING, int_vol, bias)

        return (OverlapStatus.INTERFERENCE_FAIL, int_vol, bias)

    except ImportError:
        return (OverlapStatus.CONTACT_ONLY, 0.0, 0.0)
    except Exception as exc:
        bool_failures_out.append(BooleanFailure(
            solid_a=sa.solid_id,
            solid_b=sb.solid_id,
            operation="common_volume",
            occt_message=str(exc),
        ))
        return None


def _shape_volume(shape: object) -> float:
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps

    props = GProp_GProps()
    brepgprop.VolumeProperties(shape, props)
    return float(abs(props.Mass()))
