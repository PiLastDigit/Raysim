"""Result panel — Phase B3.

Per-detector results table with overlay toggles.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QCheckBox,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from raysim.proj.schema import DetectorResult

if TYPE_CHECKING:
    from raysim.ui.state import AppState
    from raysim.ui.viewer import ViewerWidget


class ResultPanel(QDockWidget):  # type: ignore[misc]
    """Dockable results table panel."""

    def __init__(
        self, state: AppState, viewer: ViewerWidget, parent: QWidget | None = None,
    ) -> None:
        super().__init__("Results", parent)
        self._state = state
        self._viewer = viewer

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(2, 2, 2, 2)

        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels([
            "Detector", "Dose (krad)", "mm-Al Mean",
            "Angular Spread", "Stack Leaks", "Overlap Susp.",
        ])
        self._table.currentCellChanged.connect(self._on_row_changed)
        layout.addWidget(self._table)

        overlay_layout = QHBoxLayout()
        self._ray_cb = QCheckBox("3D Ray View")
        self._ray_cb.toggled.connect(self._on_ray_toggle)
        overlay_layout.addWidget(self._ray_cb)
        self._mollweide_cb = QCheckBox("Mollweide")
        self._mollweide_cb.toggled.connect(self._on_mollweide_toggle)
        overlay_layout.addWidget(self._mollweide_cb)
        self._projection_cb = QCheckBox("6-Face Projection")
        self._projection_cb.toggled.connect(self._on_projection_toggle)
        overlay_layout.addWidget(self._projection_cb)
        layout.addLayout(overlay_layout)

        self._health_label = QLabel("")
        layout.addWidget(self._health_label)

        self.setWidget(container)

        self._results: list[DetectorResult] = []
        self._ray_overlay: object | None = None
        self._mollweide_dialog: object | None = None
        self._projection_dialog: object | None = None

        self._state.run_complete.connect(self._refresh)

    def _refresh(self) -> None:
        raw = self._state.detector_results
        self._results = [r for r in raw if isinstance(r, DetectorResult)]

        self._table.setRowCount(len(self._results))
        total_leaks = 0
        total_max_hit = 0

        for i, r in enumerate(self._results):
            self._table.setItem(i, 0, QTableWidgetItem(r.detector_name))
            self._table.setItem(i, 1, QTableWidgetItem(f"{r.dose_total_krad:.3f}"))
            self._table.setItem(i, 2, QTableWidgetItem(f"{r.mm_al_equivalent_mean:.2f}"))
            self._table.setItem(i, 3, QTableWidgetItem(f"{r.angular_spread_mm_al:.2f}"))
            self._table.setItem(i, 4, QTableWidgetItem(str(r.n_stack_leak_rays)))
            self._table.setItem(i, 5, QTableWidgetItem(str(r.n_overlap_suspicious_rays)))
            total_leaks += r.n_stack_leak_rays
            total_max_hit += r.n_max_hit_rays

        self._table.resizeColumnsToContents()

        if total_leaks or total_max_hit:
            self._health_label.setText(
                f"Diagnostics: {total_leaks} stack leak(s), {total_max_hit} max-hit ray(s)"
            )
        else:
            self._health_label.setText("All detectors healthy")

    def _selected_result(self) -> DetectorResult | None:
        row: int = self._table.currentRow()
        if 0 <= row < len(self._results):
            return self._results[row]
        return None

    def _on_row_changed(self, row: int, _col: int, _prev_row: int, _prev_col: int) -> None:
        pass

    def _on_ray_toggle(self, checked: bool) -> None:
        result = self._selected_result()
        if result is None or not checked:
            if self._ray_overlay is not None:
                self._ray_overlay.clear()  # type: ignore[attr-defined]
            return
        if result.healpix_mm_al_per_pixel is not None:
            from raysim.ui.overlays.ray_overlay import RayOverlay
            if not isinstance(self._ray_overlay, RayOverlay):
                self._ray_overlay = RayOverlay(self._viewer)
            det = next(
                (d for d in self._state.detectors if d.name == result.detector_name),
                None,
            )
            if det is not None:
                self._ray_overlay.show_rays(
                    det.position_xyz_mm,
                    result.healpix_mm_al_per_pixel,
                    self._state.nside,
                    self._state.scene.bbox_diag_mm if self._state.scene else 100.0,
                )

    def _on_mollweide_toggle(self, checked: bool) -> None:
        result = self._selected_result()
        if result is None or not checked:
            if self._mollweide_dialog is not None:
                self._mollweide_dialog.close()  # type: ignore[attr-defined]
                self._mollweide_dialog = None
            return
        if result.healpix_mm_al_per_pixel is not None:
            from raysim.ui.overlays.mollweide_overlay import MollweideDialog
            dlg = MollweideDialog(
                result.healpix_mm_al_per_pixel,
                self._state.nside,
                result.detector_name,
                self,
            )
            dlg.show()
            self._mollweide_dialog = dlg

    def _on_projection_toggle(self, checked: bool) -> None:
        result = self._selected_result()
        if result is None or not checked:
            if self._projection_dialog is not None:
                self._projection_dialog.close()  # type: ignore[attr-defined]
                self._projection_dialog = None
            return
        if result.healpix_mm_al_per_pixel is not None:
            from raysim.ui.overlays.projection_overlay import ProjectionDialog
            dlg = ProjectionDialog(
                result.healpix_mm_al_per_pixel,
                self._state.nside,
                result.detector_name,
                self,
            )
            dlg.show()
            self._projection_dialog = dlg
