"""Phase 0 smoke (§0.2): embreex BVH build + closest-hit ray cast.

Verifies the *exact* embreex API surface RaySim relies on, and documents what
is NOT exposed (filter callbacks / IntersectContext) which forces design
decisions at A.4 / B1.5 — see docs/decisions/phase-0.md.
"""

from __future__ import annotations

import numpy as np
import pytest

embreex = pytest.importorskip("embreex")
trimesh = pytest.importorskip("trimesh")


@pytest.fixture()
def cube_scene():  # type: ignore[no-untyped-def]
    from embreex.mesh_construction import TriangleMesh
    from embreex.rtcore_scene import EmbreeScene

    cube = trimesh.creation.box(extents=[2.0, 2.0, 2.0])
    verts = np.asarray(cube.vertices, dtype=np.float32)
    tris = np.asarray(cube.faces, dtype=np.uint32)
    scene = EmbreeScene()
    TriangleMesh(scene, verts[tris])
    return scene


def test_intersect_returns_prim_id_or_minus_one(cube_scene) -> None:  # type: ignore[no-untyped-def]
    origins = np.array([[0, 0, 5], [0, 0, 5]], dtype=np.float32)
    dirs = np.array([[0, 0, -1], [0, 1, 0]], dtype=np.float32)
    out = cube_scene.run(origins, dirs, query="INTERSECT")
    assert out.shape == (2,)
    assert out[0] >= 0  # hit
    assert out[1] == -1  # miss


def test_distance_returns_t_or_inf(cube_scene) -> None:  # type: ignore[no-untyped-def]
    origins = np.array([[0, 0, 5]], dtype=np.float32)
    dirs = np.array([[0, 0, -1]], dtype=np.float32)
    out = cube_scene.run(origins, dirs, query="DISTANCE")
    # Cube extents [2,2,2] → top face at z=1, ray from z=5 → t=4
    assert abs(float(out[0]) - 4.0) < 1e-4


def test_occluded_query(cube_scene) -> None:  # type: ignore[no-untyped-def]
    origins = np.array([[0, 0, 5], [0, 0, 5]], dtype=np.float32)
    dirs = np.array([[0, 0, -1], [0, 1, 0]], dtype=np.float32)
    out = cube_scene.run(origins, dirs, query="OCCLUDED")
    # In embreex 4.4: 0 = hit, -1 = miss.
    assert out[0] == 0
    assert out[1] == -1


def test_filter_callback_unavailable() -> None:
    """Hard finding for Phase 0 §0.2: embreex 4.4 exposes no filter-callback API.

    This means A.4's fallback tie-batch *window query with exclusion* path is
    unimplementable on this dependency. B1.5 pre-built coincident-face groups
    become the mandatory tie-handling mechanism.
    """
    from embreex import rtcore, rtcore_scene

    exposed = set(dir(rtcore_scene)) | set(dir(rtcore))
    forbidden = {"IntersectContext", "RTCIntersectContext", "set_filter_function"}
    assert not (
        forbidden & exposed
    ), "if any of these appear, revisit the A.4 fallback decision"
