"""Ray engine — HEALPix sampling, Embree BVH, iterative closest-hit traversal.

See MVP_PLAN §5 for the module contract.
"""

from raysim.ray.healpix import HEALPY_AVAILABLE, all_pixel_directions, npix_for_nside, pix2vec
from raysim.ray.scene import (
    BuiltScene,
    PreBuiltTiedGroups,
    SolidEntry,
    load_scene,
    load_scene_from_directory,
)
from raysim.ray.tracer import DEFAULT_MAX_HITS, TraversalResult, enclosing_solids, trace_rays

__all__ = [
    "DEFAULT_MAX_HITS",
    "HEALPY_AVAILABLE",
    "BuiltScene",
    "PreBuiltTiedGroups",
    "SolidEntry",
    "TraversalResult",
    "all_pixel_directions",
    "enclosing_solids",
    "load_scene",
    "load_scene_from_directory",
    "npix_for_nside",
    "pix2vec",
    "trace_rays",
]
