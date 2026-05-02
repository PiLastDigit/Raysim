"""Assembly tree panel — Phase B3.

``QTreeWidget`` displaying the ``AssemblyNode`` hierarchy from ``load_step``.
Each node shows: name (from XCAF, or solid_id fallback), material assignment
status (icon), color swatch from XCAF color.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QDockWidget,
    QMenu,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from raysim.geom.step_loader import AssemblyNode
    from raysim.ui.state import AppState
    from raysim.ui.viewer import ViewerWidget


class TreePanel(QDockWidget):  # type: ignore[misc]
    """Dockable assembly tree panel."""

    def __init__(
        self, state: AppState, viewer: ViewerWidget, parent: QWidget | None = None,
    ) -> None:
        super().__init__("Assembly Tree", parent)
        self._state = state
        self._viewer = viewer

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Name", "Part", "Solid ID", "Material"])
        self._tree.setColumnCount(4)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._context_menu)
        self._tree.currentItemChanged.connect(self._on_selection_changed)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(self._tree)
        self.setWidget(container)

        self._leaf_items: dict[str, QTreeWidgetItem] = {}

        self._state.scene_loaded.connect(self._rebuild_tree)
        self._state.assignments_changed.connect(self._update_assignment_status)
        self._viewer.shape_selected.connect(self._on_viewer_selection)

    def _rebuild_tree(self) -> None:
        self._tree.clear()
        self._leaf_items.clear()
        root = self._state.assembly_root
        if root is None:
            return
        root_item = self._add_node(root, None)
        root_item.setExpanded(True)
        self._update_assignment_status()

    def _add_node(
        self, node: AssemblyNode, parent_item: QTreeWidgetItem | None,
    ) -> QTreeWidgetItem:
        if node.leaf is not None:
            display = node.leaf.name or node.leaf.solid_id
            part = node.leaf.part_name or ""
            item = QTreeWidgetItem([display, part, node.leaf.solid_id, ""])
            if node.leaf.color_rgb is not None:
                r, g, b = node.leaf.color_rgb
                item.setBackground(0, QBrush(QColor.fromRgbF(r, g, b)))
        else:
            display = node.name or node.path_key or "(root)"
            item = QTreeWidgetItem([display, "", "", ""])

        if parent_item is not None:
            parent_item.addChild(item)
        else:
            self._tree.addTopLevelItem(item)

        if node.leaf is not None:
            self._leaf_items[node.leaf.solid_id] = item

        for child in node.children:
            self._add_node(child, item)

        return item

    def _update_assignment_status(self) -> None:
        assignment_map = {a.solid_id: a.material_group_id for a in self._state.assignments}
        for solid_id, item in self._leaf_items.items():
            gid = assignment_map.get(solid_id, "")
            item.setText(3, gid)
            if gid:
                item.setForeground(3, QBrush(QColor("green")))
            else:
                item.setForeground(3, QBrush(QColor("red")))

    def _on_selection_changed(
        self, current: QTreeWidgetItem | None, _previous: QTreeWidgetItem | None,
    ) -> None:
        if current is None:
            return
        solid_id = current.text(2)
        if solid_id:
            self._viewer.highlight_solid(solid_id)

    def _context_menu(self, pos: object) -> None:
        item = self._tree.currentItem()
        if item is None:
            return
        solid_id = item.text(2)
        if not solid_id:
            return

        menu = QMenu(self)

        assign_menu = menu.addMenu("Assign material...")
        for mat in self._state.library.materials:
            action = assign_menu.addAction(f"{mat.group_id} ({mat.display_name})")
            action.triggered.connect(
                lambda checked, gid=mat.group_id: self._state.set_assignment(solid_id, gid)
            )

        menu.addAction("Show in viewer", lambda: self._viewer.highlight_solid(solid_id))
        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def select_solid(self, solid_id: str) -> None:
        """Programmatic selection from the viewer."""
        item = self._leaf_items.get(solid_id)
        if item is not None:
            self._tree.setCurrentItem(item)

    def _on_viewer_selection(self, solid_id: str, _shape_type: str) -> None:
        """Sync viewer selection to tree selection."""
        self.select_solid(solid_id)
