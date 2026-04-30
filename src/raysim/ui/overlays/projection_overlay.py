"""6-face unfolded box projection overlay — Phase B3.

Each face shows the mean mm-Al for HEALPix pixels in that hemisphere
quadrant, as a color-mapped rectangle.
"""

from __future__ import annotations

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtWidgets import QDialog, QVBoxLayout

from raysim.ray.healpix import all_pixel_directions


class ProjectionDialog(QDialog):  # type: ignore[misc]
    """6-face equivalent-thickness projection."""

    def __init__(
        self,
        mm_al_per_pixel: tuple[float, ...],
        nside: int,
        detector_name: str,
        parent: object | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"6-Face Projection — {detector_name}")
        self.resize(600, 450)

        layout = QVBoxLayout(self)
        fig = Figure(figsize=(6, 4), dpi=100)
        canvas = FigureCanvasQTAgg(fig)
        layout.addWidget(canvas)

        dirs = all_pixel_directions(nside)
        mm_al = np.asarray(mm_al_per_pixel, dtype=np.float64)

        faces = _classify_faces(dirs)
        face_labels = ["+X (Right)", "-X (Left)", "+Y (Front)", "-Y (Back)", "+Z (Top)", "-Z (Bottom)"]
        means = []
        for mask in faces:
            if np.any(mask):
                means.append(float(np.mean(mm_al[mask])))
            else:
                means.append(0.0)

        # 2×3 grid layout matching an unfolded box cross
        grid_positions = [
            (1, 2),  # +X right
            (1, 0),  # -X left
            (0, 1),  # +Y front -> top row center
            (2, 1),  # -Y back -> bottom row center
            (1, 1),  # +Z top -> center
            (3, 1),  # -Z bottom -> below
        ]
        grid = np.full((4, 3), np.nan)
        label_grid: list[list[str]] = [[""] * 3 for _ in range(4)]
        for i, (r, c) in enumerate(grid_positions):
            grid[r, c] = means[i]
            label_grid[r][c] = face_labels[i]

        ax = fig.add_subplot(111)
        vmin = min(m for m in means if m > 0) if any(m > 0 for m in means) else 0
        vmax = max(means) if any(m > 0 for m in means) else 1
        im = ax.imshow(grid, cmap="hot", vmin=vmin, vmax=vmax, aspect="auto")

        for r in range(4):
            for c in range(3):
                if not np.isnan(grid[r, c]):
                    ax.text(c, r, f"{label_grid[r][c]}\n{grid[r, c]:.1f}",
                            ha="center", va="center", fontsize=8, color="white")

        fig.colorbar(im, ax=ax, label="mm Al-eq", shrink=0.7)
        ax.set_title(f"{detector_name} — Face Means", fontsize=10)
        ax.set_xticks([])
        ax.set_yticks([])
        fig.tight_layout()
        canvas.draw()


def _classify_faces(dirs: np.ndarray) -> list[np.ndarray]:
    """Classify pixels by dominant direction component (6 faces)."""
    abs_dirs = np.abs(dirs)
    dominant = np.argmax(abs_dirs, axis=1)
    sign = np.sign(dirs[np.arange(len(dirs)), dominant])

    faces = []
    for axis in range(3):
        for s in [1.0, -1.0]:
            mask = (dominant == axis) & (sign == s)
            faces.append(mask)
    return faces
