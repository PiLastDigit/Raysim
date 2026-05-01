"""RaySim main window — Phase B3.

PySide6 ``QMainWindow`` with dockable panel layout and ``QSettings``
persistence for window geometry and dock arrangement.
"""

from __future__ import annotations

import sys
from pathlib import Path

import structlog
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QMessageBox,
)

from raysim import __version__
from raysim.ui.state import AppState

_LOG = structlog.get_logger(__name__)

_ORG_NAME = "RaySim"
_APP_NAME = "RaySim"


class MainWindow(QMainWindow):  # type: ignore[misc]
    """Top-level window for the RaySim desktop application."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"RaySim {__version__}")
        self.resize(1400, 900)

        self._state = AppState(self)
        self._settings = QSettings(_ORG_NAME, _APP_NAME)

        self._setup_viewer()
        self._setup_panels()
        self._setup_menus()
        self._restore_layout()

        self._state.project_changed.connect(self._update_title)
        self._state.scene_loaded.connect(self._on_scene_loaded)

    # -- viewer --------------------------------------------------------------

    def _setup_viewer(self) -> None:
        from raysim.ui.viewer import ViewerWidget

        self._viewer = ViewerWidget(self)
        self.setCentralWidget(self._viewer)

    # -- panels --------------------------------------------------------------

    def _setup_panels(self) -> None:
        from raysim.ui.panels.detector_panel import DetectorPanel
        from raysim.ui.panels.material_panel import MaterialPanel
        from raysim.ui.panels.result_panel import ResultPanel
        from raysim.ui.panels.run_panel import RunPanel
        from raysim.ui.panels.scenario_panel import ScenarioPanel
        from raysim.ui.panels.tree_panel import TreePanel

        self._tree_panel = TreePanel(self._state, self._viewer, self)
        self._material_panel = MaterialPanel(self._state, self)
        self._detector_panel = DetectorPanel(self._state, self._viewer, self)
        self._scenario_panel = ScenarioPanel(self._state, self)
        self._run_panel = RunPanel(self._state, self)
        self._result_panel = ResultPanel(self._state, self._viewer, self)

        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._tree_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._material_panel)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._detector_panel)

        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._scenario_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._result_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._run_panel)

    # -- menus ---------------------------------------------------------------

    def _setup_menus(self) -> None:
        mb = self.menuBar()

        file_menu = mb.addMenu("&File")
        file_menu.addAction("&New Project", self._on_new)
        file_menu.addAction("&Open Project...", self._on_open_project)
        file_menu.addAction("Open &STEP File...", self._on_open_step)
        file_menu.addSeparator()
        file_menu.addAction("&Save", self._on_save)
        file_menu.addAction("Save &As...", self._on_save_as)
        file_menu.addSeparator()
        file_menu.addAction("E&xit", self.close)

        view_menu = mb.addMenu("&View")
        for panel in [
            self._tree_panel, self._material_panel, self._detector_panel,
            self._scenario_panel, self._run_panel, self._result_panel,
        ]:
            view_menu.addAction(panel.toggleViewAction())  # type: ignore[attr-defined]
        view_menu.addSeparator()
        view_menu.addAction("Fit &All", self._viewer.fit_all)
        for axis in ("front", "back", "top", "bottom", "left", "right", "iso"):
            view_menu.addAction(
                axis.capitalize(),
                lambda a=axis: self._viewer.set_view_axis(a),
            )

        run_menu = mb.addMenu("&Run")
        run_menu.addAction("&Run Simulation", self._run_panel.start_run)
        run_menu.addAction("&Cancel", self._run_panel.cancel_run)

        help_menu = mb.addMenu("&Help")
        help_menu.addAction("&About", self._on_about)

    # -- slots ---------------------------------------------------------------

    def _on_new(self) -> None:
        if not self._check_dirty():
            return
        self._state.new_project()
        self._viewer.clear()

    def _on_open_project(self) -> None:
        if not self._check_dirty():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", "RaySim Projects (*.raysim);;All Files (*)"
        )
        if path:
            self._state.open_project(Path(path))

    def _on_open_step(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open STEP File", "", "STEP Files (*.step *.stp);;All Files (*)"
        )
        if path:
            self._state.open_step(Path(path))

    def _on_save(self) -> None:
        if self._state.project_path is None:
            self._on_save_as()
        else:
            self._state.save_project()

    def _on_save_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project As", "", "RaySim Projects (*.raysim);;All Files (*)"
        )
        if path:
            self._state.save_project_as(Path(path))

    def _on_about(self) -> None:
        QMessageBox.about(
            self, "About RaySim",
            f"RaySim {__version__}\n\n"
            "3D Total Ionizing Dose (TID) sector-shielding simulator\n"
            "for spacecraft.",
        )

    def _on_scene_loaded(self) -> None:
        if self._state.leaves:
            self._viewer.init_viewer()
            self._viewer.display_assembly(self._state.leaves)

    def _update_title(self) -> None:
        dirty = " *" if self._state.is_dirty else ""
        name = self._state.project_path.name if self._state.project_path else "Untitled"
        self.setWindowTitle(f"RaySim {__version__} — {name}{dirty}")

    def _check_dirty(self) -> bool:
        """Return True if safe to proceed (not dirty, or user chose to discard)."""
        if not self._state.is_dirty:
            return True
        reply = QMessageBox.question(
            self, "Unsaved Changes",
            "You have unsaved changes. Do you want to save before continuing?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Save:
            self._on_save()
            return True
        return bool(reply == QMessageBox.StandardButton.Discard)

    # -- layout persistence --------------------------------------------------

    def _restore_layout(self) -> None:
        geom = self._settings.value("window/geometry")
        if geom is not None:
            self.restoreGeometry(geom)
        state = self._settings.value("window/state")
        if state is not None:
            self.restoreState(state)

    def closeEvent(self, event: object) -> None:  # noqa: N802
        if not self._check_dirty():
            event.ignore()  # type: ignore[attr-defined]
            return
        self._settings.setValue("window/geometry", self.saveGeometry())
        self._settings.setValue("window/state", self.saveState())
        event.accept()  # type: ignore[attr-defined]


def _setup_conda_dll_path() -> None:
    """Add conda env's Library/bin to DLL search path on Windows.

    When running Python directly (without micromamba activate), OCCT's
    shared libraries in Library/bin are not on PATH. This adds them
    via os.add_dll_directory so OCCT imports don't crash silently.
    """
    import os
    import platform

    if platform.system() != "Windows":
        return
    env_root = os.path.dirname(sys.executable)
    dll_path = os.path.join(env_root, "Library", "bin")
    if os.path.isdir(dll_path):
        os.add_dll_directory(dll_path)
        os.environ["PATH"] = dll_path + ";" + os.environ.get("PATH", "")


def launch() -> None:
    """Entry point for ``raysim gui``."""
    from PySide6.QtCore import QTimer

    _setup_conda_dll_path()

    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    QTimer.singleShot(0, window._viewer.init_viewer)
    sys.exit(app.exec())
