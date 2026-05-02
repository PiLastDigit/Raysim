"""STEP file loader — Phase B1.1 + B3.0 XCAF migration.

Uses ``OCC.Core.STEPCAFControl.STEPCAFControl_Reader`` to load a STEP file
via the XCAF document framework, extracting part names, colors, and material
hints alongside geometry.  Walks the XCAF label tree into leaf
``TopoDS_Solid`` records with stable synthetic IDs (``solid_NNNN``).
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
    name: str | None = None
    part_name: str | None = None
    color_rgb: tuple[float, float, float] | None = None
    material_hint: str | None = None


@dataclass(frozen=True)
class AssemblyNode:
    """A node in the STEP assembly tree."""

    path_key: str
    children: tuple[AssemblyNode, ...]
    leaf: LeafSolid | None
    name: str | None = None


def _xcaf_available() -> bool:
    """Check whether the XCAF document framework is available."""
    try:
        from OCC.Core.STEPCAFControl import STEPCAFControl_Reader  # noqa: F401
        from OCC.Core.TDocStd import TDocStd_Document  # noqa: F401
        from OCC.Core.XCAFDoc import XCAFDoc_DocumentTool  # noqa: F401
        return True
    except ImportError:
        _LOG.info("step_loader.xcaf_imports_unavailable")
        return False


def load_step(path: str | Path) -> AssemblyNode:
    """Read a STEP file and return the assembly tree with leaf solids.

    Uses the XCAF reader when available (provides names, colors, material
    hints). Falls back to the plain STEPControl_Reader on builds where
    XCAF crashes (known issue with pythonocc-core novtk on Windows).

    Raises ``ValueError`` on empty STEP (no solids) or read failure.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"STEP file not found: {path}")

    if _xcaf_available():
        try:
            root_node = _load_step_xcaf(path)
        except Exception:
            _LOG.info("step_loader.xcaf_failed_fallback_to_plain", path=str(path))
            root_node = _load_step_plain(path)
    else:
        _LOG.info("step_loader.using_plain_reader", path=str(path))
        root_node = _load_step_plain(path)

    leaves = list(iter_leaves(root_node))
    if not leaves:
        raise ValueError(f"STEP file contains no solids: {path}")

    _LOG.info("step_loader.loaded", path=str(path), n_solids=len(leaves))
    return root_node


def _load_step_xcaf(path: Path) -> AssemblyNode:
    """Load via STEPCAFControl_Reader (XCAF — names, colors, material hints).

    Tries pythonocc's own document format (``"pythonocc-doc-step-import"``)
    first — this populates XCAF attributes (names, colors) correctly.
    Falls back to the ``TDocStd_Application`` + ``BinXCAFDrivers`` pattern
    (issue tpaviot/pythonocc-core#1428 workaround) if the primary path fails.
    """
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
    from OCC.Core.XCAFDoc import XCAFDoc_DocumentTool

    doc = _create_xcaf_document()

    reader = STEPCAFControl_Reader()
    reader.SetColorMode(True)
    reader.SetNameMode(True)
    reader.SetMatMode(True)

    status = reader.ReadFile(str(path))
    if status != IFSelect_RetDone:
        raise ValueError(f"STEP read failed (status {status}): {path}")

    reader.Transfer(doc)

    shape_tool = XCAFDoc_DocumentTool.ShapeTool(doc.Main())  # type: ignore[attr-defined]
    color_tool = XCAFDoc_DocumentTool.ColorTool(doc.Main())  # type: ignore[attr-defined]
    mat_tool = XCAFDoc_DocumentTool.MaterialTool(doc.Main())  # type: ignore[attr-defined]

    return _build_tree_xcaf(shape_tool, color_tool, mat_tool)


def _create_xcaf_document() -> object:
    """Create an XCAF document for STEPCAFControl_Reader.Transfer.

    Primary: ``TDocStd_Document("pythonocc-doc-step-import")`` — the same
    pattern pythonocc's own ``read_step_file_with_names_colors`` uses.
    This correctly populates TDataStd_Name attributes on labels.

    Fallback: ``TDocStd_Application`` + ``BinXCAFDrivers`` — the #1428
    workaround.  Works for geometry but may not populate name attributes.
    """
    from OCC.Core.TDocStd import TDocStd_Document

    try:
        doc = TDocStd_Document("pythonocc-doc-step-import")
        _LOG.info("step_loader.xcaf_doc_created", method="pythonocc-doc")
        return doc
    except Exception as exc:
        _LOG.debug("step_loader.pythonocc_doc_failed", error=str(exc))

    from OCC.Core.BinXCAFDrivers import binxcafdrivers
    from OCC.Core.TDocStd import TDocStd_Application

    app = TDocStd_Application()
    binxcafdrivers.DefineFormat(app)
    doc = TDocStd_Document("BinXCAF")
    app.NewDocument("BinXCAF", doc)
    _LOG.info("step_loader.xcaf_doc_created", method="BinXCAFDrivers")
    return doc


def _load_step_plain(path: Path) -> AssemblyNode:
    """Fallback: load via STEPControl_Reader (no XCAF metadata)."""
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.STEPControl import STEPControl_Reader
    from OCC.Core.TopAbs import TopAbs_COMPOUND, TopAbs_COMPSOLID, TopAbs_SOLID
    from OCC.Core.TopoDS import TopoDS_Iterator, topods

    reader = STEPControl_Reader()
    status = reader.ReadFile(str(path))
    if status != IFSelect_RetDone:
        raise ValueError(f"STEP read failed (status {status}): {path}")

    reader.TransferRoots()
    root_shape = reader.OneShape()
    if root_shape is None:
        raise ValueError(f"STEP file contains no shapes: {path}")

    counter = [0]

    def _walk(shape: object, prefix: str) -> AssemblyNode:
        shape_type = shape.ShapeType()  # type: ignore[attr-defined]

        if shape_type == TopAbs_SOLID:
            solid = topods.Solid(shape)
            solid_id = f"solid_{counter[0]:04d}"
            counter[0] += 1
            bbox = Bnd_Box()
            brepbndlib.Add(solid, bbox)
            xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
            leaf = LeafSolid(
                solid_id=solid_id,
                path_key=prefix or "0",
                shape=solid,
                bbox_min_mm=(xmin, ymin, zmin),
                bbox_max_mm=(xmax, ymax, zmax),
            )
            return AssemblyNode(path_key=prefix or "0", children=(), leaf=leaf)

        if shape_type in (TopAbs_COMPOUND, TopAbs_COMPSOLID):
            children: list[AssemblyNode] = []
            it = TopoDS_Iterator(shape)
            child_idx = 0
            while it.More():
                child = it.Value()
                child_prefix = f"{prefix}/{child_idx}" if prefix else str(child_idx)
                children.append(_walk(child, child_prefix))
                child_idx += 1
                it.Next()
            return AssemblyNode(
                path_key=prefix, children=tuple(children), leaf=None,
            )

        return AssemblyNode(path_key=prefix, children=(), leaf=None)

    return _walk(root_shape, "")


def iter_leaves(node: AssemblyNode) -> Iterator[LeafSolid]:
    """Depth-first, walk-order-stable iteration over leaf solids."""
    if node.leaf is not None:
        yield node.leaf
    for child in node.children:
        yield from iter_leaves(child)


def _build_tree_xcaf(
    shape_tool: object,
    color_tool: object,
    mat_tool: object,
) -> AssemblyNode:
    """Build a recursive ``AssemblyNode`` tree from the XCAF label hierarchy."""
    from OCC.Core.TDF import TDF_LabelSequence

    free_shapes = TDF_LabelSequence()
    shape_tool.GetFreeShapes(free_shapes)  # type: ignore[attr-defined]

    counter = [0]
    children: list[AssemblyNode] = []
    for i in range(free_shapes.Length()):
        label = free_shapes.Value(i + 1)
        child_prefix = str(i)
        children.append(
            _walk_label(
                label, shape_tool, color_tool, mat_tool,
                _prefix=child_prefix, _counter=counter,
            )
        )

    if len(children) == 1:
        return children[0]
    return AssemblyNode(path_key="", children=tuple(children), leaf=None)


def _walk_label(
    label: object,
    shape_tool: object,
    color_tool: object,
    mat_tool: object,
    *,
    _prefix: str,
    _counter: list[int],
    _instance_name: str | None = None,
    _accumulated_loc: object | None = None,
) -> AssemblyNode:
    """Recursively walk one XCAF label into an AssemblyNode.

    ``_instance_name`` is the component/reference label's name (e.g. "R41"),
    passed by the parent when following a reference.  The label's own name
    (e.g. "R_0402_1005Metric") is the prototype/part-definition name.
    Instance name takes priority for display; prototype becomes ``part_name``.

    ``_accumulated_loc`` carries the composed ``TopLoc_Location`` from all
    ancestor component references so leaf shapes are placed correctly in
    the assembly.
    """
    from OCC.Core.TDF import TDF_LabelSequence
    from OCC.Core.TopAbs import TopAbs_COMPOUND, TopAbs_COMPSOLID, TopAbs_SOLID

    proto_name = _get_label_name(label)
    label_name = _instance_name or proto_name
    part_name = proto_name if _instance_name else None

    if shape_tool.IsAssembly(label):  # type: ignore[attr-defined]
        children: list[AssemblyNode] = []
        components = TDF_LabelSequence()
        shape_tool.GetComponents(label, components)  # type: ignore[attr-defined]
        for i in range(components.Length()):
            comp_label = components.Value(i + 1)
            ref_label = comp_label
            comp_name: str | None = None
            child_loc = _accumulated_loc
            if shape_tool.IsReference(comp_label):  # type: ignore[attr-defined]
                comp_name = _get_label_name(comp_label)
                child_loc = _compose_location(
                    _accumulated_loc,
                    shape_tool.GetLocation(comp_label),  # type: ignore[attr-defined]
                )
                from OCC.Core.TDF import TDF_Label
                ref = TDF_Label()
                shape_tool.GetReferredShape(comp_label, ref)  # type: ignore[attr-defined]
                ref_label = ref
            child_prefix = f"{_prefix}/{i}" if _prefix else str(i)
            children.append(
                _walk_label(
                    ref_label, shape_tool, color_tool, mat_tool,
                    _prefix=child_prefix, _counter=_counter,
                    _instance_name=comp_name,
                    _accumulated_loc=child_loc,
                )
            )
        return AssemblyNode(
            path_key=_prefix, children=tuple(children), leaf=None,
            name=label_name,
        )

    if shape_tool.IsSimpleShape(label):  # type: ignore[attr-defined]
        shape = shape_tool.GetShape(label)  # type: ignore[attr-defined]
        if shape is not None:
            shape = _apply_location(shape, _accumulated_loc)
            shape_type = shape.ShapeType()  # type: ignore[attr-defined]
            if shape_type == TopAbs_SOLID:
                return _make_leaf_node(
                    shape, label, shape_tool, color_tool, mat_tool,
                    _prefix=_prefix, _counter=_counter,
                    label_name=label_name, part_name=part_name,
                )
            if shape_type in (TopAbs_COMPOUND, TopAbs_COMPSOLID):
                return _walk_compound(
                    shape, label, shape_tool, color_tool, mat_tool,
                    _prefix=_prefix, _counter=_counter,
                    label_name=label_name, part_name=part_name,
                )

    return AssemblyNode(path_key=_prefix, children=(), leaf=None, name=label_name)


def _walk_compound(
    shape: object,
    label: object,
    shape_tool: object,
    color_tool: object,
    mat_tool: object,
    *,
    _prefix: str,
    _counter: list[int],
    label_name: str | None,
    part_name: str | None = None,
) -> AssemblyNode:
    """Walk a compound/compsolid shape, extracting child solids."""
    from OCC.Core.TopAbs import TopAbs_SOLID
    from OCC.Core.TopoDS import TopoDS_Iterator, topods

    children: list[AssemblyNode] = []
    it = TopoDS_Iterator(shape)
    child_idx = 0
    while it.More():
        child = it.Value()
        child_prefix = f"{_prefix}/{child_idx}" if _prefix else str(child_idx)
        if child.ShapeType() == TopAbs_SOLID:
            solid = topods.Solid(child)
            leaf = _make_leaf(
                solid, color_tool, mat_tool, label,
                _prefix=child_prefix, _counter=_counter,
                label_name=label_name, part_name=part_name,
            )
            children.append(
                AssemblyNode(path_key=child_prefix, children=(), leaf=leaf)
            )
        else:
            children.append(
                _walk_compound(
                    child, label, shape_tool, color_tool, mat_tool,
                    _prefix=child_prefix, _counter=_counter,
                    label_name=label_name, part_name=part_name,
                )
            )
        child_idx += 1
        it.Next()

    return AssemblyNode(
        path_key=_prefix, children=tuple(children), leaf=None,
        name=label_name,
    )


def _make_leaf_node(
    shape: object,
    label: object,
    shape_tool: object,
    color_tool: object,
    mat_tool: object,
    *,
    _prefix: str,
    _counter: list[int],
    label_name: str | None,
    part_name: str | None = None,
) -> AssemblyNode:
    """Create a leaf AssemblyNode for a single solid."""
    from OCC.Core.TopoDS import topods

    solid = topods.Solid(shape)
    leaf = _make_leaf(
        solid, color_tool, mat_tool, label,
        _prefix=_prefix, _counter=_counter,
        label_name=label_name, part_name=part_name,
    )
    return AssemblyNode(path_key=_prefix, children=(), leaf=leaf, name=label_name)


def _make_leaf(
    solid: object,
    color_tool: object,
    mat_tool: object,
    label: object,
    *,
    _prefix: str,
    _counter: list[int],
    label_name: str | None,
    part_name: str | None = None,
) -> LeafSolid:
    """Create a LeafSolid with bbox, color, and material hint."""
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib

    solid_id = f"solid_{_counter[0]:04d}"
    _counter[0] += 1

    bbox = Bnd_Box()
    brepbndlib.Add(solid, bbox)
    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()

    color = _get_color(color_tool, label)
    mat_hint = _get_material_name(mat_tool, label)

    return LeafSolid(
        solid_id=solid_id,
        path_key=_prefix or "0",
        shape=solid,
        bbox_min_mm=(xmin, ymin, zmin),
        bbox_max_mm=(xmax, ymax, zmax),
        name=label_name,
        part_name=part_name,
        color_rgb=color,
        material_hint=mat_hint,
    )


def _compose_location(
    parent: object | None, child: object,
) -> object:
    """Compose two ``TopLoc_Location`` objects, handling a null parent."""
    if parent is None:
        return child
    return parent.Multiplied(child)  # type: ignore[attr-defined]


def _apply_location(shape: object, loc: object | None) -> object:
    """Apply an accumulated ``TopLoc_Location`` to a shape.

    Uses ``BRepBuilderAPI_Transform`` to bake the placement into the
    geometry (same approach as pythonocc's ``read_step_file_with_names_colors``).
    """
    if loc is None or loc.IsIdentity():  # type: ignore[attr-defined]
        return shape
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform

    return BRepBuilderAPI_Transform(
        shape, loc.Transformation(),  # type: ignore[attr-defined]
    ).Shape()


def _get_label_name(label: object) -> str | None:
    """Extract the name attribute from an XCAF label.

    Uses ``TDF_Label.GetLabelName()`` (the same method pythonocc's own
    ``read_step_file_with_names_colors`` uses).  Falls back to the
    ``TDataStd_Name`` attribute lookup if ``GetLabelName`` is unavailable.
    """
    try:
        name = label.GetLabelName()  # type: ignore[attr-defined]
        if name:
            s = str(name).strip()
            if s:
                return s
    except Exception:
        pass

    try:
        from OCC.Core.TDataStd import TDataStd_Name

        name_attr = TDataStd_Name()
        if label.FindAttribute(TDataStd_Name.GetID(), name_attr):  # type: ignore[attr-defined]
            text = name_attr.Get()
            if text:
                s = str(text).strip()
                if s:
                    return s
    except Exception:
        pass
    return None


def _get_material_name(mat_tool: object, label: object) -> str | None:
    """Extract the material name from an XCAF label via MaterialTool."""
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
    """Extract the color from an XCAF label via ColorTool."""
    from OCC.Core.Quantity import Quantity_Color
    from OCC.Core.XCAFDoc import XCAFDoc_ColorGen

    c = Quantity_Color()
    try:
        if color_tool.GetColor(label, XCAFDoc_ColorGen, c):  # type: ignore[attr-defined]
            return (c.Red(), c.Green(), c.Blue())
    except Exception:
        pass
    return None
