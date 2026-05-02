"""QThread worker for on-demand geometry validation — Phase B3/v0.4.0.

Runs ``diagnose_overlaps`` in a background thread so the UI stays
responsive during the O(N²) volume classification.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, Signal

if TYPE_CHECKING:
    from raysim.ui.state import AppState


class ValidateWorker(QThread):  # type: ignore[misc]
    """Runs the full overlap diagnostic off the GUI thread."""

    validation_complete = Signal(object)
    validation_error = Signal(str)

    def __init__(self, state: AppState, parent: object | None = None) -> None:
        super().__init__(parent)
        self._state = state

    def run(self) -> None:
        try:
            report = self._state.validate_geometry()
            self.validation_complete.emit(report)
        except Exception as exc:
            self.validation_error.emit(str(exc))
