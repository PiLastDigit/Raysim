"""STEP file loader — Phase B1.1.

Wraps ``OCC.Core.STEPControl.STEPControl_Reader`` to load a STEP file and
walk its compound into leaf ``TopoDS_Solid`` records with stable synthetic
IDs (``solid_NNNN``).  Per-part names/colors/layers from XCAF are deferred
to B2.2 (blocked by the ``XCAFDoc_DocumentTool`` bootstrap regression
documented in ``docs/decisions/phase-0.md``).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import structlog

_LOG = structlog.get_logger(__name__)


@dataclass(frozen=True)
class LeafSolid:
    """One leaf solid extracted from a STEP compound."""

    solid_id: str
    path_key: str
    shape: object  # TopoDS_Solid
    bbox_min_mm: tuple[float, float, float]
    bbox_max_mm: tuple[float, float, float]


@dataclass(frozen=True)
class AssemblyNode:
    """A node in the STEP assembly tree."""

    path_key: str
    children: tuple[AssemblyNode, ...]
    leaf: LeafSolid | None


def load_step(path: str | Path) -> AssemblyNode:
    """Read a STEP file and return the assembly tree with leaf solids.

    Raises ``ValueError`` on empty STEP (no solids) or read failure.
    """
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.STEPControl import STEPControl_Reader

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"STEP file not found: {path}")

    reader = STEPControl_Reader()
    status = reader.ReadFile(str(path))
    if status != IFSelect_RetDone:
        raise ValueError(f"STEP read failed (status {status}): {path}")

    reader.TransferRoots()
    root_shape = reader.OneShape()
    if root_shape is None:
        raise ValueError(f"STEP file contains no shapes: {path}")

    root_node = _build_tree(root_shape)
    leaves = list(iter_leaves(root_node))
    if not leaves:
        raise ValueError(f"STEP file contains no solids: {path}")

    _LOG.info("step_loader.loaded", path=str(path), n_solids=len(leaves))
    return root_node


def iter_leaves(node: AssemblyNode) -> Iterator[LeafSolid]:
    """Depth-first, walk-order-stable iteration over leaf solids."""
    if node.leaf is not None:
        yield node.leaf
    for child in node.children:
        yield from iter_leaves(child)


def _build_tree(
    shape: object, *, _prefix: str = "", _counter: list[int] | None = None,
) -> AssemblyNode:
    """Build a recursive ``AssemblyNode`` tree from a ``TopoDS_Shape``."""
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    from OCC.Core.TopAbs import TopAbs_COMPOUND, TopAbs_COMPSOLID, TopAbs_SOLID
    from OCC.Core.TopoDS import TopoDS_Iterator, topods

    if _counter is None:
        _counter = [0]

    shape_type = shape.ShapeType()  # type: ignore[attr-defined]

    if shape_type == TopAbs_SOLID:
        solid = topods.Solid(shape)
        solid_id = f"solid_{_counter[0]:04d}"
        _counter[0] += 1

        bbox = Bnd_Box()
        brepbndlib.Add(solid, bbox)
        xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()

        leaf = LeafSolid(
            solid_id=solid_id,
            path_key=_prefix or "0",
            shape=solid,
            bbox_min_mm=(xmin, ymin, zmin),
            bbox_max_mm=(xmax, ymax, zmax),
        )
        return AssemblyNode(path_key=_prefix or "0", children=(), leaf=leaf)

    if shape_type in (TopAbs_COMPOUND, TopAbs_COMPSOLID):
        children: list[AssemblyNode] = []
        it = TopoDS_Iterator(shape)
        child_idx = 0
        while it.More():
            child = it.Value()
            child_prefix = f"{_prefix}/{child_idx}" if _prefix else str(child_idx)
            children.append(_build_tree(
                child, _prefix=child_prefix, _counter=_counter,
            ))
            child_idx += 1
            it.Next()
        return AssemblyNode(path_key=_prefix, children=tuple(children), leaf=None)

    # Fallback: use _extract_leaves for other shape types.
    leaves = _extract_leaves(shape, _prefix=_prefix, _counter=_counter)
    leaf_children = tuple(
        AssemblyNode(path_key=leaf.path_key, children=(), leaf=leaf)
        for leaf in leaves
    )
    return AssemblyNode(path_key=_prefix, children=leaf_children, leaf=None)


def _extract_leaves(
    shape: object, *, _prefix: str = "", _counter: list[int] | None = None,
) -> list[LeafSolid]:
    """Walk a TopoDS_Shape recursively, extracting TopoDS_Solid leaves.

    Path keys reflect the recursive walk path (e.g. ``"0/2/1"``).
    ``solid_id`` is assigned sequentially across the whole tree.
    """
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    from OCC.Core.TopAbs import TopAbs_COMPOUND, TopAbs_COMPSOLID, TopAbs_SOLID
    from OCC.Core.TopoDS import TopoDS_Iterator, topods

    if _counter is None:
        _counter = [0]

    solids: list[LeafSolid] = []
    shape_type = shape.ShapeType()  # type: ignore[attr-defined]

    if shape_type == TopAbs_SOLID:
        solid = topods.Solid(shape)
        solid_id = f"solid_{_counter[0]:04d}"
        _counter[0] += 1

        bbox = Bnd_Box()
        brepbndlib.Add(solid, bbox)
        xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()

        solids.append(
            LeafSolid(
                solid_id=solid_id,
                path_key=_prefix or "0",
                shape=solid,
                bbox_min_mm=(xmin, ymin, zmin),
                bbox_max_mm=(xmax, ymax, zmax),
            )
        )
    elif shape_type in (TopAbs_COMPOUND, TopAbs_COMPSOLID):
        it = TopoDS_Iterator(shape)
        child_idx = 0
        while it.More():
            child = it.Value()
            child_prefix = f"{_prefix}/{child_idx}" if _prefix else str(child_idx)
            solids.extend(_extract_leaves(
                child, _prefix=child_prefix, _counter=_counter,
            ))
            child_idx += 1
            it.Next()
    else:
        # Try TopExp_Explorer for other shape types that may contain solids.
        from OCC.Core.TopExp import TopExp_Explorer

        explorer = TopExp_Explorer(shape, TopAbs_SOLID)
        child_idx = 0
        while explorer.More():
            solid = topods.Solid(explorer.Current())
            child_prefix = f"{_prefix}/{child_idx}" if _prefix else str(child_idx)
            solid_id = f"solid_{_counter[0]:04d}"
            _counter[0] += 1

            bbox = Bnd_Box()
            brepbndlib.Add(solid, bbox)
            xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()

            solids.append(
                LeafSolid(
                    solid_id=solid_id,
                    path_key=child_prefix,
                    shape=solid,
                    bbox_min_mm=(xmin, ymin, zmin),
                    bbox_max_mm=(xmax, ymax, zmax),
                )
            )
            child_idx += 1
            explorer.Next()

    return solids
