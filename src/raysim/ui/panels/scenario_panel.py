"""Scenario panel — Phase B3.

``.dos`` file picker, inline DDC preview (matplotlib), and Nside spinbox.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from raysim.ui.state import AppState


class ScenarioPanel(QDockWidget):  # type: ignore[misc]
    """Dockable scenario panel with .dos picker and DDC preview."""

    def __init__(self, state: AppState, parent: QWidget | None = None) -> None:
        super().__init__("Scenario", parent)
        self._state = state

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(2, 2, 2, 2)

        file_layout = QHBoxLayout()
        self._file_label = QLabel("No dose curve loaded")
        file_layout.addWidget(self._file_label)
        self._browse_btn = QPushButton("Browse...")
        self._browse_btn.clicked.connect(self._on_browse)
        file_layout.addWidget(self._browse_btn)
        layout.addLayout(file_layout)

        nside_layout = QHBoxLayout()
        nside_layout.addWidget(QLabel("Nside:"))
        self._nside_spin = QSpinBox()
        self._nside_spin.setRange(1, 256)
        self._nside_spin.setValue(64)
        self._nside_spin.valueChanged.connect(self._on_nside_changed)
        nside_layout.addWidget(self._nside_spin)
        layout.addLayout(nside_layout)

        self._canvas: QWidget | None = None
        self._figure = None
        try:
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
            from matplotlib.figure import Figure

            self._figure = Figure(figsize=(4, 3), dpi=80)
            self._canvas = FigureCanvasQTAgg(self._figure)
            layout.addWidget(self._canvas)
        except ImportError:
            layout.addWidget(QLabel("(matplotlib not available — no DDC preview)"))

        self._metadata_table = QTableWidget()
        self._metadata_table.setColumnCount(2)
        self._metadata_table.setHorizontalHeaderLabels(["Key", "Value"])
        self._metadata_table.setMaximumHeight(120)
        layout.addWidget(self._metadata_table)

        self.setWidget(container)

        self._state.scenario_changed.connect(self._refresh_preview)

    def _on_browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Dose Curve", "", "OMERE DOS Files (*.dos);;All Files (*)"
        )
        if path:
            self._state.load_dose_curve(Path(path))
            self._file_label.setText(Path(path).name)

    def _on_nside_changed(self, value: int) -> None:
        self._state.set_nside(value)

    def _refresh_preview(self) -> None:
        spline = self._state.dose_spline
        if spline is None or self._figure is None:
            return

        self._figure.clear()
        ax = self._figure.add_subplot(111)
        t = np.geomspace(spline.t_min_mm_al, spline.t_max_mm_al, 200)
        d_total = spline.dose_total(t)
        ax.loglog(t, d_total, "k-", linewidth=2, label="Total")

        for sp_name in spline.species_names:
            d_sp = spline.dose_species(sp_name, t)
            if np.any(d_sp > 0):
                ax.loglog(t, d_sp, "--", label=sp_name, alpha=0.7)

        ax.set_xlabel("mm Al-eq")
        ax.set_ylabel("krad(Si)")
        ax.set_title("Dose-Depth Curve")
        ax.legend(fontsize=7)
        ax.grid(True, which="both", alpha=0.3)
        self._figure.tight_layout()
        if self._canvas is not None:
            self._canvas.draw()

        metadata = spline.mission_metadata
        self._metadata_table.setRowCount(len(metadata))
        for i, (k, v) in enumerate(sorted(metadata.items())):
            self._metadata_table.setItem(i, 0, QTableWidgetItem(str(k)))
            self._metadata_table.setItem(i, 1, QTableWidgetItem(str(v)))
