"""STEP material-tag ingestion — Phase B2.2.

OCCT-dependent. Imports ``pythonocc-core`` at call time (not at module level).
Tests guarded by ``pytest.importorskip("OCC.Core")``.

Correlation with B1 leaf solids uses a two-gate verification (leaf count +
bbox fingerprint) to avoid attaching tags to wrong solids when the XCAF and
STEPControl readers produce different walk orders.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from raysim.mat.library import MaterialLibrary

if TYPE_CHECKING:
    from raysim.geom.step_loader import LeafSolid

_LOG = structlog.get_logger(__name__)

_BBOX_TOL_MM = 1e-3


@dataclass(frozen=True)
class StepMaterialTag:
    """Material tag extracted from STEP XCAF attributes."""

    solid_id: str
    material_name: str | None
    color_rgb: tuple[float, float, float] | None


@dataclass(frozen=True)
class TagMatch:
    """Result of matching a STEP tag to a library entry."""

    solid_id: str
    matched_group_id: str | None
    confidence: float
    raw_tag: str


def extract_step_tags(
    step_path: Path,
    leaves: Sequence[LeafSolid],
) -> list[StepMaterialTag]:
    """Extract material names and colors from a STEP file via XCAF.

    Correlates XCAF leaves with B1's ``LeafSolid`` list by DFS walk-order
    index, verified by a leaf-count + bbox-fingerprint gate.
    """
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
    from OCC.Core.TCollection import TCollection_ExtendedString
    from OCC.Core.TDF import TDF_LabelSequence
    from OCC.Core.TDocStd import TDocStd_Document
    from OCC.Core.TopAbs import TopAbs_SOLID
    from OCC.Core.XCAFDoc import XCAFDoc_DocumentTool

    handle = TDocStd_Document(TCollection_ExtendedString("XDE"))
    reader = STEPCAFControl_Reader()
    reader.SetColorMode(True)
    reader.SetNameMode(True)
    reader.SetMatMode(True)

    status = reader.ReadFile(str(step_path))
    if status != IFSelect_RetDone:
        _LOG.warning("step_tags.read_failed", path=str(step_path), status=status)
        return []

    reader.Transfer(handle)

    shape_tool = XCAFDoc_DocumentTool.ShapeTool(handle.Main())
    color_tool = XCAFDoc_DocumentTool.ColorTool(handle.Main())
    mat_tool = XCAFDoc_DocumentTool.MaterialTool(handle.Main())

    # Collect XCAF leaf solids in DFS order.
    xcaf_leaves: list[tuple[str | None, tuple[float, float, float] | None, tuple[float, ...]]] = []

    free_shapes = TDF_LabelSequence()
    shape_tool.GetFreeShapes(free_shapes)

    def _walk_labels(label_seq: TDF_LabelSequence) -> None:
        for i in range(label_seq.Length()):
            label = label_seq.Value(i + 1)
            if shape_tool.IsSimpleShape(label):
                shape = shape_tool.GetShape(label)
                if shape is not None and shape.ShapeType() == TopAbs_SOLID:
                    mat_name = _get_material_name(mat_tool, label)
                    color = _get_color(color_tool, label)
                    bbox = _get_bbox(shape)
                    xcaf_leaves.append((mat_name, color, bbox))
            if shape_tool.IsAssembly(label):
                children = TDF_LabelSequence()
                shape_tool.GetComponents(label, children)
                _walk_labels(children)

    _walk_labels(free_shapes)

    # Verification gate 1: count.
    if len(xcaf_leaves) != len(leaves):
        _LOG.warning(
            "step_tags.count_mismatch",
            xcaf_count=len(xcaf_leaves),
            b1_count=len(leaves),
            path=str(step_path),
        )
        return []

    # Verification gate 2: bbox fingerprint.
    for i, (_, _, xcaf_bbox) in enumerate(xcaf_leaves):
        b1 = leaves[i]
        b1_flat = (*b1.bbox_min_mm, *b1.bbox_max_mm)
        if not _bbox_close(xcaf_bbox, b1_flat):
            _LOG.warning(
                "step_tags.bbox_mismatch",
                index=i,
                xcaf_bbox=xcaf_bbox,
                b1_bbox=b1_flat,
            )
            return []

    # Zip tags to B1 solid_ids.
    tags: list[StepMaterialTag] = []
    for i, (mat_name, color, _) in enumerate(xcaf_leaves):
        tags.append(StepMaterialTag(
            solid_id=leaves[i].solid_id,
            material_name=mat_name,
            color_rgb=color,
        ))

    _LOG.info("step_tags.extracted", n_tags=len(tags), path=str(step_path))
    return tags


def _bbox_close(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    if len(a) != len(b):
        return False
    return all(math.isclose(x, y, abs_tol=_BBOX_TOL_MM) for x, y in zip(a, b, strict=True))


def _get_bbox(shape: object) -> tuple[float, ...]:
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib

    bbox = Bnd_Box()
    brepbndlib.Add(shape, bbox)
    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
    return (xmin, ymin, zmin, xmax, ymax, zmax)


def _get_material_name(mat_tool: object, label: object) -> str | None:
    from OCC.Core.TCollection import TCollection_HAsciiString

    name = TCollection_HAsciiString("")
    desc = TCollection_HAsciiString("")
    density = [0.0]
    dense_name = TCollection_HAsciiString("")
    dense_val_type = TCollection_HAsciiString("")
    try:
        if mat_tool.GetMaterial(label, name, desc, density, dense_name, dense_val_type):  # type: ignore[attr-defined]
            text = name.String() if name else None
            if text:
                return str(text)
    except Exception:
        pass
    return None


def _get_color(color_tool: object, label: object) -> tuple[float, float, float] | None:
    from OCC.Core.Quantity import Quantity_Color
    from OCC.Core.XCAFDoc import XCAFDoc_ColorGen

    c = Quantity_Color()
    try:
        if color_tool.GetColor(label, XCAFDoc_ColorGen, c):  # type: ignore[attr-defined]
            return (c.Red(), c.Green(), c.Blue())
    except Exception:
        pass
    return None


def match_tags_to_library(
    tags: Sequence[StepMaterialTag],
    library: MaterialLibrary,
    *,
    threshold: float = 0.7,
) -> list[TagMatch]:
    """Fuzzy-match STEP material name strings to library entries."""
    results: list[TagMatch] = []
    for tag in tags:
        if tag.material_name is None or not tag.material_name.strip():
            results.append(TagMatch(
                solid_id=tag.solid_id,
                matched_group_id=None,
                confidence=0.0,
                raw_tag=tag.material_name or "",
            ))
            continue

        raw = tag.material_name
        best_id: str | None = None
        best_score = 0.0

        normalized = raw.lower().strip()
        for mat in library.materials:
            score = _similarity(normalized, mat.group_id.lower(), mat.display_name.lower())
            if score > best_score:
                best_score = score
                best_id = mat.group_id

        results.append(TagMatch(
            solid_id=tag.solid_id,
            matched_group_id=best_id if best_score >= threshold else None,
            confidence=best_score,
            raw_tag=raw,
        ))

    return results


def _similarity(query: str, group_id: str, display_name: str) -> float:
    """Simple substring/containment similarity score in [0, 1]."""
    if query in (group_id, display_name):
        return 1.0
    if query in group_id or group_id in query:
        return 0.8
    if query in display_name or display_name in query:
        return 0.8
    tokens_q = set(query.replace("-", " ").replace("_", " ").split())
    tokens_g = set(group_id.replace("-", " ").replace("_", " ").split())
    tokens_d = set(display_name.replace("-", " ").replace("_", " ").split())
    overlap_g = len(tokens_q & tokens_g) / max(len(tokens_q | tokens_g), 1)
    overlap_d = len(tokens_q & tokens_d) / max(len(tokens_q | tokens_d), 1)
    return max(overlap_g, overlap_d)
