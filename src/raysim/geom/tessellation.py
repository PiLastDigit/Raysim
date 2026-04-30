"""Tessellation of TopoDS_Solid via BRepMesh — Phase B1.2.

Runs ``BRepMesh_IncrementalMesh`` on each leaf solid extracted by
:mod:`raysim.geom.step_loader`, then walks the shell→face hierarchy to
extract per-shell triangle arrays in float64.  The ``TopoDS_Solid`` handle
is kept alive on ``TessellatedSolid.shape`` so B1.3's healer can operate
on the same shape without reloading the STEP.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import structlog
from numpy.typing import NDArray

from raysim.geom.step_loader import LeafSolid

_LOG = structlog.get_logger(__name__)


@dataclass(frozen=True)
class TessellatedShell:
    """Per-shell triangle arrays extracted from a tessellated solid."""

    shell_index: int
    vertices: NDArray[np.float64]   # (n_v, 3)
    faces: NDArray[np.int64]        # (n_t, 3)
    triangle_normals: NDArray[np.float64]  # (n_t, 3) unit-length


@dataclass(frozen=True)
class TessellatedSolid:
    """A tessellated STEP solid with per-shell triangle grouping."""

    solid_id: str
    shape: object  # TopoDS_Solid — kept alive for B1.3's healer
    shells: tuple[TessellatedShell, ...]
    bbox_min_mm: tuple[float, float, float]
    bbox_max_mm: tuple[float, float, float]


def tessellate(
    leaf: LeafSolid,
    *,
    linear_mm: float = 0.1,
    angular_rad: float = 0.5,
) -> TessellatedSolid:
    """Tessellate a ``LeafSolid`` and return per-shell triangle arrays."""
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh

    shape = leaf.shape
    mesh = BRepMesh_IncrementalMesh(shape, linear_mm, False, angular_rad, True)
    mesh.Perform()
    if not mesh.IsDone():
        raise RuntimeError(f"BRepMesh failed on {leaf.solid_id}")

    shells = _extract_shells(shape)
    if not shells:
        _LOG.warning("tessellation.empty", solid_id=leaf.solid_id)

    _LOG.debug(
        "tessellation.done",
        solid_id=leaf.solid_id,
        n_shells=len(shells),
        n_triangles=sum(s.faces.shape[0] for s in shells),
    )
    return TessellatedSolid(
        solid_id=leaf.solid_id,
        shape=shape,
        shells=tuple(shells),
        bbox_min_mm=leaf.bbox_min_mm,
        bbox_max_mm=leaf.bbox_max_mm,
    )


def flatten_index(
    solid: TessellatedSolid,
    shell_index: int,
    prim_in_shell: int,
) -> int:
    """Convert ``(shell_index, prim_in_shell)`` to the solid's flat triangle index."""
    offset = sum(
        int(solid.shells[i].faces.shape[0])
        for i in range(shell_index)
    )
    return offset + prim_in_shell


def _extract_shells(shape: object) -> list[TessellatedShell]:
    """Walk shell→face hierarchy, extracting triangulation per shell."""
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_FORWARD, TopAbs_SHELL
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopLoc import TopLoc_Location

    shells: list[TessellatedShell] = []
    shell_idx = 0
    shell_exp = TopExp_Explorer(shape, TopAbs_SHELL)

    while shell_exp.More():
        shell_shape = shell_exp.Current()
        all_verts: list[NDArray[np.float64]] = []
        all_faces: list[NDArray[np.int64]] = []
        vert_offset = 0

        face_exp = TopExp_Explorer(shell_shape, TopAbs_FACE)
        while face_exp.More():
            face = face_exp.Current()
            loc = TopLoc_Location()
            tri = BRep_Tool.Triangulation(face, loc)

            if tri is None:
                face_exp.Next()
                continue

            n_nodes = tri.NbNodes()
            n_tris = tri.NbTriangles()
            transform = loc.Transformation()

            # Extract vertices with location transform applied.
            verts = np.empty((n_nodes, 3), dtype=np.float64)
            for i in range(1, n_nodes + 1):
                pnt = tri.Node(i)
                pnt.Transform(transform)
                verts[i - 1] = [pnt.X(), pnt.Y(), pnt.Z()]

            # Extract triangles, honoring face orientation.
            is_forward = face.Orientation() == TopAbs_FORWARD
            faces = np.empty((n_tris, 3), dtype=np.int64)
            for i in range(1, n_tris + 1):
                t = tri.Triangle(i)
                n1, n2, n3 = t.Get()
                if is_forward:
                    faces[i - 1] = [n1 - 1 + vert_offset, n2 - 1 + vert_offset,
                                    n3 - 1 + vert_offset]
                else:
                    faces[i - 1] = [n1 - 1 + vert_offset, n3 - 1 + vert_offset,
                                    n2 - 1 + vert_offset]

            all_verts.append(verts)
            all_faces.append(faces)
            vert_offset += n_nodes
            face_exp.Next()

        if all_verts:
            combined_verts = np.vstack(all_verts)
            combined_faces = np.vstack(all_faces)
            normals = _compute_unit_normals(combined_verts, combined_faces)
            shells.append(TessellatedShell(
                shell_index=shell_idx,
                vertices=combined_verts,
                faces=combined_faces,
                triangle_normals=normals,
            ))

        shell_idx += 1
        shell_exp.Next()

    return shells


def _compute_unit_normals(
    verts: NDArray[np.float64], faces: NDArray[np.int64],
) -> NDArray[np.float64]:
    """Compute unit-length triangle normals in float64."""
    v0 = verts[faces[:, 0]]
    v1 = verts[faces[:, 1]]
    v2 = verts[faces[:, 2]]
    n = np.cross(v1 - v0, v2 - v0)
    norm = np.linalg.norm(n, axis=1, keepdims=True)
    norm = np.where(norm == 0, 1.0, norm)
    return (n / norm).astype(np.float64, copy=False)
