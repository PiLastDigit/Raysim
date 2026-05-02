"""OCCT AIS 3D viewer widget — Phase B3.

Wraps pythonocc-core's qtViewer3d for embedding in the PySide6 main window.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from PySide6.QtCore import Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QVBoxLayout, QWidget

if TYPE_CHECKING:
    from raysim.geom.step_loader import LeafSolid

_LOG = structlog.get_logger(__name__)


class ViewerWidget(QWidget):  # type: ignore[misc]
    """Embeds the OCCT qtViewer3d and exposes a shape-display API."""

    shape_selected = Signal(str, str)
    position_picked = Signal(float, float, float)
    normal_picked = Signal(float, float, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        self._viewer: Any = None
        self._display: Any = None
        self._solid_shapes: dict[str, object] = {}
        self._solid_ais: dict[str, object] = {}
        self._snap_mode: str = "centroid"

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._display is not None:
            self._display.View.MustBeResized()

    def init_viewer(self) -> None:
        """Create the OCCT viewer and initialize OpenGL (call after show)."""
        if self._viewer is not None:
            return

        from OCC.Display.backend import load_backend
        load_backend("pyside6")
        from OCC.Display.qtDisplay import qtViewer3d

        self._viewer = qtViewer3d(self)
        self._layout.addWidget(self._viewer)
        self._viewer.InitDriver()
        self._display = self._viewer._display
        self._setup_selection_callback()

        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, self._deferred_resize)

    def _deferred_resize(self) -> None:
        """Force OCCT to pick up the actual widget size after layout settles."""
        if self._display is not None:
            self._display.View.MustBeResized()
            self._display.FitAll()

    def _setup_selection_callback(self) -> None:
        """Register click handler for solid selection and face-centroid picking."""
        def _on_select(shp: object, *_args: object) -> None:
            if shp is None:
                return
            for solid_id, ais_obj in self._solid_ais.items():
                if solid_id.startswith("detector_"):
                    continue
                try:
                    if ais_obj.Shape().IsSame(shp):  # type: ignore[attr-defined]
                        pos = _snap_position(shp, self._snap_mode)
                        if pos is not None:
                            self.position_picked.emit(*pos)
                        normal = _face_normal_at_centroid(shp)
                        if normal is not None:
                            self.normal_picked.emit(*normal)
                        self.shape_selected.emit(solid_id, "face")
                        break
                except Exception:
                    pass

        self._display.register_select_callback(_on_select)

    def set_snap_mode(self, mode: str) -> None:
        """Set snap mode: 'centroid', 'vertex', 'edge_midpoint', or 'free'."""
        self._snap_mode = mode

    @property
    def display(self) -> object:
        return self._display

    def pick_position_from_click(self, screen_x: int, screen_y: int) -> tuple[float, float, float] | None:
        """Convert a screen click to a 3D position via OCCT projection."""
        try:
            view = self._display.View
            x, y, z = view.Convert(screen_x, screen_y)
            return (float(x), float(y), float(z))
        except Exception:
            return None

    def display_assembly(self, leaves: list[LeafSolid]) -> None:
        """Display all leaf solids from a loaded assembly."""
        from OCC.Core.AIS import AIS_Shape
        from OCC.Core.Quantity import (
            Quantity_Color,
            Quantity_TOC_RGB,
        )

        self.clear()
        context = self._display.Context

        for leaf in leaves:
            shape = leaf.shape
            ais = AIS_Shape(shape)

            if leaf.color_rgb is not None:
                r, g, b = leaf.color_rgb
                color = Quantity_Color(r, g, b, Quantity_TOC_RGB)
                ais.SetColor(color)

            context.Display(ais, False)
            self._solid_shapes[leaf.solid_id] = shape
            self._solid_ais[leaf.solid_id] = ais

        context.UpdateCurrentViewer()
        self.fit_all()

    def clear(self) -> None:
        if self._display is not None:
            self._display.EraseAll()
        self._solid_shapes.clear()
        self._solid_ais.clear()

    def fit_all(self) -> None:
        if self._display is not None:
            self._display.FitAll()

    def set_view_axis(self, axis: str) -> None:
        """Set camera to a named axis view."""
        view_map = {
            "front": self._display.View_Front,
            "back": self._display.View_Rear,
            "top": self._display.View_Top,
            "bottom": self._display.View_Bottom,
            "left": self._display.View_Left,
            "right": self._display.View_Right,
            "iso": self._display.View_Iso,
        }
        fn = view_map.get(axis)
        if fn:
            fn()

    def highlight_solid(self, solid_id: str) -> None:
        ais = self._solid_ais.get(solid_id)
        if ais is None:
            return
        context = self._display.Context
        context.ClearSelected(False)
        context.AddOrRemoveSelected(ais, True)

    def set_solid_color(self, solid_id: str, rgb: tuple[float, float, float]) -> None:
        from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB

        ais = self._solid_ais.get(solid_id)
        if ais is None:
            return
        color = Quantity_Color(rgb[0], rgb[1], rgb[2], Quantity_TOC_RGB)
        ais.SetColor(color)  # type: ignore[attr-defined]
        self._display.Context.UpdateCurrentViewer()

    def set_solid_transparency(self, solid_id: str, alpha: float) -> None:
        ais = self._solid_ais.get(solid_id)
        if ais is None:
            return
        ais.SetTransparency(alpha)  # type: ignore[attr-defined]
        self._display.Context.UpdateCurrentViewer()

    def display_detector_glyph(
        self, name: str, position: tuple[float, float, float], radius: float = 3.0,
    ) -> None:
        """Display a small sphere at the detector position."""
        from OCC.Core.AIS import AIS_Shape
        from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeSphere
        from OCC.Core.gp import gp_Pnt
        from OCC.Core.Quantity import Quantity_Color, Quantity_NOC_RED

        sphere = BRepPrimAPI_MakeSphere(gp_Pnt(*position), radius).Shape()
        ais = AIS_Shape(sphere)
        ais.SetColor(Quantity_Color(Quantity_NOC_RED))
        self._display.Context.Display(ais, True)
        self._solid_ais[f"detector_{name}"] = ais

    def remove_detector_glyph(self, name: str) -> None:
        key = f"detector_{name}"
        ais = self._solid_ais.pop(key, None)
        if ais is not None:
            self._display.Context.Remove(ais, True)


def _snap_position(shp: object, mode: str) -> tuple[float, float, float] | None:
    """Compute snapped position based on mode."""
    if mode == "vertex":
        return _nearest_vertex(shp)
    if mode == "edge_midpoint":
        return _edge_midpoint(shp)
    if mode == "free":
        return _face_centroid(shp)
    return _face_centroid(shp)


def _nearest_vertex(shp: object) -> tuple[float, float, float] | None:
    """Return the first vertex of a shape."""
    try:
        from OCC.Core.BRep import BRep_Tool
        from OCC.Core.TopAbs import TopAbs_VERTEX
        from OCC.Core.TopExp import TopExp_Explorer

        explorer = TopExp_Explorer(shp, TopAbs_VERTEX)
        if explorer.More():
            from OCC.Core.TopoDS import topods
            vertex = topods.Vertex(explorer.Current())
            pnt = BRep_Tool.Pnt(vertex)
            return (pnt.X(), pnt.Y(), pnt.Z())
    except Exception:
        pass
    return _face_centroid(shp)


def _edge_midpoint(shp: object) -> tuple[float, float, float] | None:
    """Return the midpoint of the first edge of a shape."""
    try:
        from OCC.Core.BRep import BRep_Tool
        from OCC.Core.TopAbs import TopAbs_EDGE
        from OCC.Core.TopExp import TopExp_Explorer
        from OCC.Core.TopoDS import topods

        explorer = TopExp_Explorer(shp, TopAbs_EDGE)
        if explorer.More():
            edge = topods.Edge(explorer.Current())
            curve, first, last = BRep_Tool.Curve(edge)
            mid_param = (first + last) / 2.0
            pnt = curve.Value(mid_param)
            return (pnt.X(), pnt.Y(), pnt.Z())
    except Exception:
        pass
    return _face_centroid(shp)


def _face_centroid(shp: object) -> tuple[float, float, float] | None:
    """Compute the center of mass of a shape (face or solid)."""
    try:
        from OCC.Core.BRepGProp import brepgprop
        from OCC.Core.GProp import GProp_GProps

        props = GProp_GProps()
        brepgprop.SurfaceProperties(shp, props)
        cm = props.CentreOfMass()
        return (cm.X(), cm.Y(), cm.Z())
    except Exception:
        try:
            from OCC.Core.Bnd import Bnd_Box
            from OCC.Core.BRepBndLib import brepbndlib

            bbox = Bnd_Box()
            brepbndlib.Add(shp, bbox)
            xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
            return (
                (xmin + xmax) / 2.0,
                (ymin + ymax) / 2.0,
                (zmin + zmax) / 2.0,
            )
        except Exception:
            return None


def _face_normal_at_centroid(shp: object) -> tuple[float, float, float] | None:
    """Compute the outward normal at the centroid of a face."""
    try:
        from OCC.Core.BRep import BRep_Tool
        from OCC.Core.BRepGProp import brepgprop
        from OCC.Core.GeomLProp import GeomLProp_SLProps
        from OCC.Core.GProp import GProp_GProps
        from OCC.Core.TopAbs import TopAbs_FACE
        from OCC.Core.TopoDS import topods

        if shp.ShapeType() != TopAbs_FACE:  # type: ignore[attr-defined]
            return None
        face = topods.Face(shp)
        surface = BRep_Tool.Surface(face)
        props = GProp_GProps()
        brepgprop.SurfaceProperties(face, props)
        cm = props.CentreOfMass()
        slprops = GeomLProp_SLProps(surface, 1, 1e-6)
        slprops.SetParameters(cm.X(), cm.Y())
        if slprops.IsNormalDefined():
            n = slprops.Normal()
            return (n.X(), n.Y(), n.Z())
    except Exception:
        pass
    return (0.0, 0.0, 1.0)
