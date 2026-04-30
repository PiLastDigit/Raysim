"""3D ray-view overlay — Phase B3.

Renders 3D lines from the detector position along each HEALPix direction,
colored by accumulated mm-Al-equivalent (blue = thin, red = thick).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from raysim.ui.viewer import ViewerWidget


class RayOverlay:
    """Manages AIS ray lines in the viewer."""

    def __init__(self, viewer: ViewerWidget) -> None:
        self._viewer = viewer
        self._ais_objects: list[object] = []

    def show_rays(
        self,
        origin: tuple[float, float, float],
        mm_al_per_pixel: tuple[float, ...],
        nside: int,
        bbox_diag: float,
    ) -> None:
        """Render ray lines colored by mm-Al-equivalent."""
        self.clear()

        from OCC.Core.AIS import AIS_Shape
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
        from OCC.Core.gp import gp_Pnt
        from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB

        from raysim.ray.healpix import all_pixel_directions

        dirs = all_pixel_directions(nside)
        mm_al = np.asarray(mm_al_per_pixel, dtype=np.float64)
        vmax = float(np.max(mm_al)) if np.any(mm_al > 0) else 1.0

        context = self._viewer.display.Context  # type: ignore[attr-defined]
        p0 = gp_Pnt(*origin)

        for i in range(min(len(mm_al), len(dirs))):
            d = dirs[i]
            length = bbox_diag
            p1 = gp_Pnt(
                origin[0] + d[0] * length,
                origin[1] + d[1] * length,
                origin[2] + d[2] * length,
            )
            edge = BRepBuilderAPI_MakeEdge(p0, p1).Edge()
            ais = AIS_Shape(edge)

            frac = float(mm_al[i]) / vmax if vmax > 0 else 0.0
            r = min(frac * 2.0, 1.0)
            b = min((1.0 - frac) * 2.0, 1.0)
            color = Quantity_Color(r, 0.0, b, Quantity_TOC_RGB)
            ais.SetColor(color)
            ais.SetWidth(1.0)

            context.Display(ais, False)
            self._ais_objects.append(ais)

        context.UpdateCurrentViewer()

    def clear(self) -> None:
        if not self._ais_objects:
            return
        context = self._viewer.display.Context  # type: ignore[attr-defined]
        for ais in self._ais_objects:
            context.Remove(ais, False)
        self._ais_objects.clear()
        context.UpdateCurrentViewer()
