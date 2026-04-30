"""Mollweide projection overlay — Phase B3.

Matplotlib-only Mollweide projection of the per-pixel mm-Al array.
Uses RING ordering → theta/phi conversion.
"""

from __future__ import annotations

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtWidgets import QDialog, QVBoxLayout


class MollweideDialog(QDialog):  # type: ignore[misc]
    """Mollweide projection of the per-pixel mm-Al-equivalent map."""

    def __init__(
        self,
        mm_al_per_pixel: tuple[float, ...],
        nside: int,
        detector_name: str,
        parent: object | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Mollweide — {detector_name}")
        self.resize(700, 400)

        layout = QVBoxLayout(self)
        fig = Figure(figsize=(8, 4), dpi=100)
        canvas = FigureCanvasQTAgg(fig)
        layout.addWidget(canvas)

        ax = fig.add_subplot(111, projection="mollweide")

        npix = len(mm_al_per_pixel)
        mm_al = np.asarray(mm_al_per_pixel, dtype=np.float64)

        ipix = np.arange(npix)
        theta, phi = _pix2ang_ring(nside, ipix)
        lon = phi - np.pi
        lat = np.pi / 2.0 - theta

        sc = ax.scatter(lon, lat, c=mm_al, s=2, cmap="hot", alpha=0.8)
        fig.colorbar(sc, ax=ax, label="mm Al-eq", shrink=0.7)
        ax.set_title(f"{detector_name}  (Nside={nside})", fontsize=10)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        canvas.draw()


def _pix2ang_ring(nside: int, ipix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Convert RING-ordered pixel indices to (theta, phi) in radians."""
    npix = 12 * nside * nside
    theta = np.empty(len(ipix), dtype=np.float64)
    phi = np.empty(len(ipix), dtype=np.float64)

    for idx_pos, pix in enumerate(ipix):
        if pix < 2 * nside * (nside - 1):
            # North polar cap
            p_h = (pix + 1) / 2.0
            j = int(np.floor(np.sqrt(p_h - np.sqrt(np.floor(p_h)))) + 1)
            if j < 1:
                j = 1
            while 2 * j * (j - 1) >= pix + 1:
                j -= 1
            while 2 * j * (j + 1) < pix + 1:
                j += 1
            i_ring = j
            s = pix + 1 - 2 * i_ring * (i_ring - 1)
            theta[idx_pos] = np.arccos(1.0 - i_ring * i_ring / (3.0 * nside * nside))
            phi[idx_pos] = (s - 0.5) * np.pi / (2.0 * i_ring)
        elif pix < 2 * nside * (nside - 1) + 4 * nside * (2 * nside + 1):
            # Equatorial belt
            p_eq = pix - 2 * nside * (nside - 1)
            i_ring = p_eq // (4 * nside) + nside
            s = p_eq % (4 * nside) + 1
            shift = 0.5 * ((i_ring - nside) % 2)
            theta[idx_pos] = np.arccos((2.0 * nside - i_ring) / (1.5 * nside))
            phi[idx_pos] = (s - 0.5 - shift) * np.pi / (2.0 * nside)
        else:
            # South polar cap
            p_s = npix - pix
            j = int(np.floor(np.sqrt(p_s / 2.0 - np.sqrt(np.floor(p_s / 2.0)))) + 1)
            if j < 1:
                j = 1
            while 2 * j * (j - 1) >= p_s:
                j -= 1
            while 2 * j * (j + 1) < p_s:
                j += 1
            i_ring_from_south = j
            s = p_s - 2 * i_ring_from_south * (i_ring_from_south - 1)
            theta[idx_pos] = np.arccos(-1.0 + i_ring_from_south * i_ring_from_south / (3.0 * nside * nside))
            phi[idx_pos] = (s - 0.5) * np.pi / (2.0 * i_ring_from_south)

    return theta, phi
