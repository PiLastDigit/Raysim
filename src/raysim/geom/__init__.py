"""Geometry pipeline — STEP ingest, tessellation, healing, validation.

Import-safe without ``pythonocc-core``: the dataclasses and type definitions
are always available; functions that need OCC import it at call time and
raise a clear ``RuntimeError`` if unavailable.
"""

from raysim.geom.adapter import (
    ExportedSolid,
    GeomValidationError,
    build_scene_from_step,
    export_assembly_to_stl,
)
from raysim.geom.healing import HealedShell, HealedSolid, ShellRole, heal_assembly
from raysim.geom.overlap import (
    COPLANAR_NORMAL_TOL_RAD,
    COPLANAR_PLANE_TOL_REL,
    COVERAGE_EPSILON,
    NESTED_VOLUME_REL,
    VERTEX_MATCH_TOL_REL,
    ZERO_VOLUME_REL,
    BooleanFailure,
    MismatchedContactRegion,
    OverlapPair,
    OverlapReport,
    OverlapStatus,
    TiedTrianglePair,
    diagnose_overlaps,
)
from raysim.geom.pipeline import ValidatedAssembly, ValidationOverrides, build_assembly_from_step
from raysim.geom.step_loader import AssemblyNode, LeafSolid, iter_leaves, load_step
from raysim.geom.tessellation import TessellatedShell, TessellatedSolid, flatten_index, tessellate
from raysim.geom.watertightness import (
    ShellWatertightness,
    WatertightnessReport,
    validate_watertightness,
)

__all__ = [
    "COPLANAR_NORMAL_TOL_RAD",
    "COPLANAR_PLANE_TOL_REL",
    "COVERAGE_EPSILON",
    "NESTED_VOLUME_REL",
    "VERTEX_MATCH_TOL_REL",
    "ZERO_VOLUME_REL",
    "AssemblyNode",
    "BooleanFailure",
    "ExportedSolid",
    "GeomValidationError",
    "HealedShell",
    "HealedSolid",
    "LeafSolid",
    "MismatchedContactRegion",
    "OverlapPair",
    "OverlapReport",
    "OverlapStatus",
    "ShellRole",
    "ShellWatertightness",
    "TessellatedShell",
    "TessellatedSolid",
    "TiedTrianglePair",
    "ValidatedAssembly",
    "ValidationOverrides",
    "WatertightnessReport",
    "build_assembly_from_step",
    "build_scene_from_step",
    "diagnose_overlaps",
    "export_assembly_to_stl",
    "flatten_index",
    "heal_assembly",
    "iter_leaves",
    "load_step",
    "tessellate",
    "validate_watertightness",
]
