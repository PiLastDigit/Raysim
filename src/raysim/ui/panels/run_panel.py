"""Run panel — Phase B3.

Run button, progress bar, cancel, and status label.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from raysim.ui.state import AppState


class RunPanel(QDockWidget):  # type: ignore[misc]
    """Dockable run controls panel."""

    def __init__(self, state: AppState, parent: QWidget | None = None) -> None:
        super().__init__("Run", parent)
        self._state = state
        self._worker: object | None = None
        self._validate_worker: object | None = None

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(2, 2, 2, 2)

        self._status_label = QLabel("Ready")
        layout.addWidget(self._status_label)

        self._progress = QProgressBar()
        self._progress.setValue(0)
        layout.addWidget(self._progress)

        self._validate_btn = QPushButton("Validate Geometry")
        self._validate_btn.clicked.connect(self._start_validation)
        self._validate_btn.setEnabled(False)
        layout.addWidget(self._validate_btn)

        self._run_btn = QPushButton("Run Simulation")
        self._run_btn.clicked.connect(self.start_run)
        layout.addWidget(self._run_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self.cancel_run)
        layout.addWidget(self._cancel_btn)

        self.setWidget(container)

        self._state.gating_changed.connect(self._update_run_button)
        self._state.scenario_changed.connect(self._update_run_button)
        self._state.scene_loaded.connect(self._update_validate_button)
        self._update_run_button()

    def _update_run_button(self) -> None:
        gating = self._state.gating
        has_spline = self._state.dose_spline is not None
        has_detectors = len(self._state.detectors) > 0
        ready = (gating is not None and gating.ready) and has_spline and has_detectors
        self._run_btn.setEnabled(ready)
        if not ready:
            reasons = []
            if gating is None or not gating.ready:
                reasons.append("materials not fully assigned")
            if not has_spline:
                reasons.append("no dose curve loaded")
            if not has_detectors:
                reasons.append("no detectors placed")
            self._status_label.setText(f"Not ready: {'; '.join(reasons)}")
        else:
            self._status_label.setText("Ready")

    def _update_validate_button(self) -> None:
        self._validate_btn.setEnabled(
            self._state.step_path is not None and self._validate_worker is None
        )

    def _start_validation(self) -> None:
        if self._validate_worker is not None:
            return
        self._validate_btn.setEnabled(False)
        self._status_label.setText("Validating geometry...")

        from raysim.ui.workers.validate_worker import ValidateWorker

        self._validate_geom_rev = self._state.geometry_revision
        worker = ValidateWorker(self._state, self)
        worker.validation_complete.connect(self._on_validation_complete)
        worker.validation_error.connect(self._on_validation_error)
        worker.start()
        self._validate_worker = worker

    def _on_validation_complete(self, report: object) -> None:
        self._validate_worker = None
        self._validate_btn.setEnabled(True)

        from raysim.geom.overlap import OverlapReport
        if not isinstance(report, OverlapReport):
            self._status_label.setText("No geometry loaded")
            return

        if self._state.geometry_revision != self._validate_geom_rev:
            self._status_label.setText("Validation discarded (geometry changed)")
            return

        self._state.set_overlap_report(report)

        n_fail = len(report.failed())
        n_warn = len(report.warnings())
        n_pairs = len(report.pairs)
        summary = f"Validated: {n_pairs} pairs, {n_fail} fail, {n_warn} warn"
        self._status_label.setText(summary)

        if n_fail > 0 or n_warn > 0:
            QMessageBox.warning(
                self, "Geometry Validation",
                f"{n_fail} interference failure(s), {n_warn} warning(s).\n"
                "Check the console log for details.",
            )
        else:
            QMessageBox.information(
                self, "Geometry Validation",
                f"Clean: {n_pairs} pair(s) checked, no interference.",
            )

    def _on_validation_error(self, message: str) -> None:
        self._validate_worker = None
        self._validate_btn.setEnabled(True)
        self._status_label.setText(f"Validation error: {message}")

    def start_run(self) -> None:
        if self._worker is not None:
            return

        from pathlib import Path

        out_path_str, _ = QFileDialog.getSaveFileName(
            self, "Save run.json", "run.json", "JSON Files (*.json);;All Files (*)"
        )
        if not out_path_str:
            return
        output_path = Path(out_path_str)

        try:
            ctx = self._state.build_run_context(output_path=output_path)
        except RuntimeError as e:
            QMessageBox.warning(self, "Cannot Run", str(e))
            return

        from raysim.ui.workers.run_worker import RunContext, RunWorker

        if not isinstance(ctx, RunContext):
            return

        n_det = len(ctx.detectors)
        self._progress.setMaximum(n_det)
        self._progress.setValue(0)
        self._status_label.setText(f"Running (detector 0/{n_det})")
        self._run_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)

        worker = RunWorker(ctx, self)
        worker.detector_done.connect(self._on_detector_done)
        worker.run_complete.connect(self._on_run_complete)
        worker.run_error.connect(self._on_run_error)
        worker.start()
        self._worker = worker
        self._state.run_started.emit()

    def cancel_run(self) -> None:
        if self._worker is not None:
            self._worker.requestInterruption()  # type: ignore[attr-defined]

    def _on_detector_done(self, index: int, _result: object) -> None:
        n_det = self._progress.maximum()
        self._progress.setValue(index + 1)
        self._status_label.setText(f"Running (detector {index + 1}/{n_det})")

    def _on_run_complete(self, run_result: object) -> None:
        self._worker = None
        self._run_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self._status_label.setText("Complete")
        self._progress.setValue(self._progress.maximum())

        from raysim.proj.schema import RunResult
        if isinstance(run_result, RunResult):
            self._state.set_detector_results(list(run_result.detectors))

    def _on_run_error(self, message: str) -> None:
        self._worker = None
        self._run_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self._status_label.setText(f"Error: {message}")
        self._progress.setValue(0)
