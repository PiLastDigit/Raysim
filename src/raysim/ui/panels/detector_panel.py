"""Detector placement panel — Phase B3.

Point-detector placement with click-pick and snap modes.
Box template deferred — see plan §5.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from raysim.proj.schema import Detector

if TYPE_CHECKING:
    from raysim.ui.state import AppState
    from raysim.ui.viewer import ViewerWidget


class DetectorPanel(QDockWidget):  # type: ignore[misc]
    """Dockable detector list and placement controls."""

    def __init__(
        self, state: AppState, viewer: ViewerWidget, parent: QWidget | None = None,
    ) -> None:
        super().__init__("Detectors", parent)
        self._state = state
        self._viewer = viewer
        self._counter = 0
        self._last_normal: tuple[float, float, float] = (0.0, 0.0, 1.0)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(2, 2, 2, 2)

        self._list = QListWidget()
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._context_menu)
        self._list.currentRowChanged.connect(self._on_selection_changed)
        layout.addWidget(self._list)

        coord_layout = QHBoxLayout()
        coord_layout.addWidget(QLabel("X:"))
        self._x_spin = QDoubleSpinBox()
        self._x_spin.setRange(-1e6, 1e6)
        coord_layout.addWidget(self._x_spin)
        coord_layout.addWidget(QLabel("Y:"))
        self._y_spin = QDoubleSpinBox()
        self._y_spin.setRange(-1e6, 1e6)
        coord_layout.addWidget(self._y_spin)
        coord_layout.addWidget(QLabel("Z:"))
        self._z_spin = QDoubleSpinBox()
        self._z_spin.setRange(-1e6, 1e6)
        coord_layout.addWidget(self._z_spin)
        layout.addLayout(coord_layout)

        offset_layout = QHBoxLayout()
        snap_layout = QHBoxLayout()
        snap_layout.addWidget(QLabel("Snap:"))
        self._snap_combo = QComboBox()
        self._snap_combo.addItems(["Face centroid", "Vertex", "Edge midpoint", "Free position"])
        snap_layout.addWidget(self._snap_combo)
        layout.addLayout(snap_layout)

        offset_layout.addWidget(QLabel("Normal offset (mm):"))
        self._offset_spin = QDoubleSpinBox()
        self._offset_spin.setRange(0.0, 100.0)
        self._offset_spin.setValue(0.0)
        offset_layout.addWidget(self._offset_spin)
        layout.addLayout(offset_layout)

        btn_layout = QHBoxLayout()
        self._add_btn = QPushButton("Add Detector")
        self._add_btn.clicked.connect(self._on_add)
        btn_layout.addWidget(self._add_btn)
        self._remove_btn = QPushButton("Remove")
        self._remove_btn.clicked.connect(self._on_remove)
        btn_layout.addWidget(self._remove_btn)
        layout.addLayout(btn_layout)

        self._pick_btn = QPushButton("Pick on Geometry")
        self._pick_btn.setCheckable(True)
        self._pick_btn.setToolTip("Click a face in the viewer to place a detector at its centroid")
        btn_layout.addWidget(self._pick_btn)

        self.setWidget(container)

        self._state.detectors_changed.connect(self._refresh_list)
        self._viewer.position_picked.connect(self._on_position_picked)
        self._viewer.normal_picked.connect(self._on_normal_picked)
        self._snap_combo.currentIndexChanged.connect(self._on_snap_changed)

    def _refresh_list(self) -> None:
        self._list.clear()
        for det in self._state.detectors:
            pos = det.position_xyz_mm
            self._list.addItem(
                f"{det.name}  ({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f})"
            )

    def _on_add(self) -> None:
        self._counter += 1
        name = f"Detector_{self._counter}"
        x = self._x_spin.value()
        y = self._y_spin.value()
        z = self._z_spin.value()
        det = Detector(name=name, position_xyz_mm=(x, y, z))
        self._state.add_detector(det)
        self._viewer.display_detector_glyph(name, (x, y, z))

    def _on_remove(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        detectors = self._state.detectors
        if row < len(detectors):
            name = detectors[row].name
            self._state.remove_detector(name)
            self._viewer.remove_detector_glyph(name)

    def _on_selection_changed(self, row: int) -> None:
        if row < 0:
            return
        detectors = self._state.detectors
        if row < len(detectors):
            det = detectors[row]
            self._viewer.highlight_solid(f"detector_{det.name}")

    def _context_menu(self, pos: object) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        row = self._list.currentRow()
        detectors = self._state.detectors
        if row >= len(detectors):
            return

        menu = QMenu(self)
        menu.addAction("Delete", self._on_remove)
        menu.exec(self._list.viewport().mapToGlobal(pos))

    def _on_snap_changed(self, index: int) -> None:
        mode_map = {0: "centroid", 1: "vertex", 2: "edge_midpoint", 3: "free"}
        self._viewer.set_snap_mode(mode_map.get(index, "centroid"))

    def _on_normal_picked(self, nx: float, ny: float, nz: float) -> None:
        """Store the last picked face normal for offset application."""
        self._last_normal = (nx, ny, nz)

    def _on_position_picked(self, x: float, y: float, z: float) -> None:
        """Place a detector at the picked position with normal-offset (when pick mode active)."""
        if not self._pick_btn.isChecked():
            return

        offset = self._offset_spin.value()
        nx, ny, nz = self._last_normal
        x += nx * offset
        y += ny * offset
        z += nz * offset
        self._counter += 1
        name = f"Detector_{self._counter}"
        det = Detector(name=name, position_xyz_mm=(x, y, z))
        self._state.add_detector(det)
        self._viewer.display_detector_glyph(name, (x, y, z))
        self._pick_btn.setChecked(False)
