"""Material library + assignment panel — Phase B3.

Shows the seeded material library and assignment status.  Wired to B2's
``MaterialLibrary``, ``AssignmentReview``, and ``build_review()``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from raysim.ui.state import AppState


class MaterialPanel(QDockWidget):  # type: ignore[misc]
    """Dockable material library and assignment status panel."""

    def __init__(self, state: AppState, parent: QWidget | None = None) -> None:
        super().__init__("Materials", parent)
        self._state = state

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(2, 2, 2, 2)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels([
            "Group ID", "Display Name", "Density", "Z_eff", "Assigned",
        ])
        layout.addWidget(self._table)

        self._status_label = QLabel("No geometry loaded")
        layout.addWidget(self._status_label)

        btn_layout = QHBoxLayout()
        self._accept_btn = QPushButton("Accept All Suggestions")
        self._accept_btn.clicked.connect(self._on_accept_all)
        btn_layout.addWidget(self._accept_btn)

        self._clear_btn = QPushButton("Clear All")
        self._clear_btn.clicked.connect(self._on_clear_all)
        btn_layout.addWidget(self._clear_btn)

        layout.addLayout(btn_layout)
        self.setWidget(container)

        self._refresh_table()
        self._state.scene_loaded.connect(self._refresh_status)
        self._state.assignments_changed.connect(self._refresh_status)

    def _refresh_table(self) -> None:
        lib = self._state.library
        self._table.setRowCount(len(lib.materials))

        for i, mat in enumerate(lib.materials):
            self._table.setItem(i, 0, QTableWidgetItem(mat.group_id))
            self._table.setItem(i, 1, QTableWidgetItem(mat.display_name))
            self._table.setItem(i, 2, QTableWidgetItem(f"{mat.density_g_cm3:.2f}"))
            self._table.setItem(i, 3, QTableWidgetItem(
                f"{mat.z_eff:.1f}" if mat.z_eff is not None else ""
            ))
            count = sum(
                1 for a in self._state.assignments if a.material_group_id == mat.group_id
            )
            self._table.setItem(i, 4, QTableWidgetItem(str(count)))

        self._table.resizeColumnsToContents()

    def _refresh_status(self) -> None:
        self._refresh_table()
        review = self._state.review
        if review is None:
            self._status_label.setText("No geometry loaded")
            return
        self._status_label.setText(
            f"Auto-matched: {review.n_auto_matched}  |  "
            f"Ambiguous: {review.n_ambiguous}  |  "
            f"Unassigned: {review.n_unassigned}"
        )

    def _on_accept_all(self) -> None:
        self._state.accept_all_suggestions()

    def _on_clear_all(self) -> None:
        self._state.clear_all_assignments()
