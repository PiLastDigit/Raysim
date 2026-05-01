"""Application state controller — Phase B3.

Central owner of the mutable application state.  All panels read from and
write to this controller — they do not hold independent copies.
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from PySide6.QtCore import QObject, Signal

from raysim import __version__
from raysim.dose.spline import DoseSpline
from raysim.env.importers.omere_dos import import_omere_dos
from raysim.mat.gating import GatingResult, check_run_readiness
from raysim.mat.library import MaterialLibrary, load_library
from raysim.mat.review import AssignmentReview, build_review, review_to_assignments
from raysim.mat.rules import SolidRef, apply_rules, load_rules
from raysim.mat.step_tags import extract_step_tags, match_tags_to_library
from raysim.proj.hashing import hash_canonical, hash_file
from raysim.proj.project import (
    GeometryRef,
    ProjectFile,
    load_project,
    save_project,
)
from raysim.proj.schema import Detector, MaterialAssignment

if TYPE_CHECKING:
    from raysim.geom.step_loader import AssemblyNode, LeafSolid
    from raysim.ray.scene import BuiltScene

_LOG = structlog.get_logger(__name__)

_KEY_LIBRARIES = (
    "numpy", "scipy", "trimesh", "embreex", "healpy", "pydantic",
    "click", "structlog",
)


def _library_versions() -> dict[str, str]:
    out: dict[str, str] = {}
    for name in _KEY_LIBRARIES:
        with contextlib.suppress(PackageNotFoundError):
            out[name] = version(name)
    return out


class AppState(QObject):  # type: ignore[misc]
    """Central owner of the mutable application state."""

    project_changed = Signal()
    scene_loaded = Signal()
    assignments_changed = Signal()
    detectors_changed = Signal()
    scenario_changed = Signal()
    run_started = Signal()
    run_complete = Signal()
    gating_changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._project_path: Path | None = None
        self._project: ProjectFile | None = None
        self._dirty: bool = False

        self._assembly_root: AssemblyNode | None = None
        self._leaves: list[LeafSolid] = []
        self._scene: BuiltScene | None = None
        self._step_path: Path | None = None

        self._library: MaterialLibrary = load_library()
        self._review: AssignmentReview | None = None
        self._assignments: list[MaterialAssignment] = []

        self._detectors: list[Detector] = []
        self._dose_spline: DoseSpline | None = None
        self._dose_curve_path: Path | None = None

        self._nside: int = 64
        self._gating: GatingResult | None = None

        self._detector_results: list[object] = []
        self._last_scene_error: str | None = None

    # -- properties ----------------------------------------------------------

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    @property
    def project(self) -> ProjectFile | None:
        return self._project

    @property
    def project_path(self) -> Path | None:
        return self._project_path

    @property
    def assembly_root(self) -> AssemblyNode | None:
        return self._assembly_root

    @property
    def leaves(self) -> list[LeafSolid]:
        return self._leaves

    @property
    def scene(self) -> BuiltScene | None:
        return self._scene

    @property
    def library(self) -> MaterialLibrary:
        return self._library

    @property
    def review(self) -> AssignmentReview | None:
        return self._review

    @property
    def assignments(self) -> list[MaterialAssignment]:
        return list(self._assignments)

    @property
    def detectors(self) -> list[Detector]:
        return list(self._detectors)

    @property
    def dose_spline(self) -> DoseSpline | None:
        return self._dose_spline

    @property
    def nside(self) -> int:
        return self._nside

    @property
    def gating(self) -> GatingResult | None:
        return self._gating

    @property
    def detector_results(self) -> list[object]:
        return list(self._detector_results)

    @property
    def step_path(self) -> Path | None:
        return self._step_path

    # -- project lifecycle ---------------------------------------------------

    def new_project(self) -> None:
        self._project = None
        self._project_path = None
        self._dirty = False
        self._assembly_root = None
        self._leaves = []
        self._scene = None
        self._step_path = None
        self._assignments = []
        self._review = None
        self._detectors = []
        self._dose_spline = None
        self._dose_curve_path = None
        self._detector_results = []
        self._gating = None
        self.project_changed.emit()

    def open_project(self, path: Path) -> None:
        project = load_project(path)
        self._project = project
        self._project_path = path
        self._dirty = False
        self._assignments = list(project.assignments)
        self._detectors = list(project.detectors)
        if project.dose_curve_path:
            dose_path = path.parent / project.dose_curve_path
            if dose_path.exists():
                self._load_dose_curve(dose_path)
        geom_path = path.parent / project.geometry.path
        if geom_path.exists() and geom_path.suffix.lower() in (".step", ".stp"):
            self.open_step(geom_path)
        self._dirty = False
        self.project_changed.emit()
        self.assignments_changed.emit()
        self.detectors_changed.emit()

    def save_project(self) -> None:
        if self._project_path is None:
            return
        self._save_to(self._project_path)

    def save_project_as(self, path: Path) -> None:
        self._project_path = path
        self._save_to(path)

    def _save_to(self, path: Path) -> None:
        geom_ref = self._build_geometry_ref(path.parent)
        now_utc = self._project.created_at_utc if self._project and self._project.created_at_utc else datetime.now(UTC).isoformat()

        sources: dict[str, str] = {}
        if self._review:
            for s in self._review.statuses:
                if s.material_group_id is not None:
                    sources[s.solid_id] = s.source

        project = ProjectFile(
            geometry=geom_ref,
            assignments=tuple(self._assignments),
            assignment_sources=sources,
            detectors=tuple(self._detectors),
            dose_curve_path=str(self._dose_curve_path.relative_to(path.parent) if self._dose_curve_path and self._dose_curve_path.is_relative_to(path.parent) else self._dose_curve_path) if self._dose_curve_path else None,
            dose_curve_sha256=hash_file(self._dose_curve_path) if self._dose_curve_path else None,
            created_at_utc=now_utc,
            raysim_version=__version__,
        )
        save_project(project, path)
        self._project = project
        self._dirty = False
        self.project_changed.emit()

    def _build_geometry_ref(self, base_dir: Path) -> GeometryRef:
        if self._step_path is None:
            return GeometryRef(path="(none)", sha256="0" * 64)
        rel = str(self._step_path.relative_to(base_dir)) if self._step_path.is_relative_to(base_dir) else str(self._step_path)
        return GeometryRef(
            path=rel,
            sha256=hash_file(self._step_path),
        )

    # -- geometry lifecycle --------------------------------------------------

    def open_step(self, path: Path) -> None:
        from raysim.geom.step_loader import iter_leaves, load_step

        self._step_path = path
        root = load_step(path)
        self._assembly_root = root
        self._leaves = list(iter_leaves(root))

        self._run_auto_assignment()
        self._scene = None
        self._update_gating()
        self._mark_dirty()
        self.scene_loaded.emit()

    def _rebuild_scene(self) -> None:
        """Rebuild the BuiltScene from the current STEP + assignments.

        Tolerates incomplete assignments (KeyError/ValueError from the
        scene loader when solid_id doesn't map to a material). Real
        backend failures (STEP parse, tessellation, OCC) propagate.
        """
        if self._step_path is None:
            return
        from raysim.geom.adapter import build_scene_from_step

        materials_list = list(self._library.materials)
        try:
            scene, _assembly = build_scene_from_step(
                self._step_path,
                materials=materials_list,
                assignments=self._assignments or None,
                accept_warnings=True,
                accept_watertightness_failures=True,
            )
            self._scene = scene
            self._last_scene_error = None
        except KeyError as exc:
            _LOG.warning(
                "state.rebuild_scene_incomplete_assignments",
                step_path=str(self._step_path),
                error=str(exc),
            )
            self._scene = None
            self._last_scene_error = f"Incomplete assignments: {exc}"

    def reload_step(self) -> None:
        if self._step_path is not None:
            self.open_step(self._step_path)

    # -- material assignment -------------------------------------------------

    def _run_auto_assignment(self) -> None:
        if not self._leaves:
            return

        solid_refs = [
            SolidRef(
                solid_id=leaf.solid_id,
                path_key=leaf.path_key,
                display_name=leaf.name or leaf.solid_id,
            )
            for leaf in self._leaves
        ]

        tags = extract_step_tags(self._leaves)
        tag_matches = match_tags_to_library(tags, self._library)

        rules = load_rules()
        rule_matches = apply_rules(rules, solid_refs)

        self._review = build_review(
            solid_refs,
            tag_matches=tag_matches,
            rule_matches=rule_matches,
            manual_assignments=self._assignments or None,
            library=self._library,
        )

        try:
            self._assignments = review_to_assignments(self._review)
        except ValueError:
            self._assignments = [
                MaterialAssignment(solid_id=s.solid_id, material_group_id=s.material_group_id)
                for s in self._review.statuses
                if s.material_group_id is not None
            ]

        self.assignments_changed.emit()

    def set_assignment(self, solid_id: str, group_id: str) -> None:
        self._assignments = [a for a in self._assignments if a.solid_id != solid_id]
        self._assignments.append(MaterialAssignment(solid_id=solid_id, material_group_id=group_id))
        self._scene = None
        self._update_gating()
        self._mark_dirty()
        self.assignments_changed.emit()

    def accept_all_suggestions(self) -> None:
        if self._review is None:
            return
        for s in self._review.statuses:
            if s.material_group_id is not None and s.source != "manual":
                existing = {a.solid_id for a in self._assignments}
                if s.solid_id not in existing:
                    self._assignments.append(
                        MaterialAssignment(solid_id=s.solid_id, material_group_id=s.material_group_id)
                    )
        self._scene = None
        self._update_gating()
        self._mark_dirty()
        self.assignments_changed.emit()

    def clear_all_assignments(self) -> None:
        self._assignments = []
        self._scene = None
        self._update_gating()
        self._mark_dirty()
        self.assignments_changed.emit()

    # -- detectors -----------------------------------------------------------

    def add_detector(self, detector: Detector) -> None:
        self._detectors.append(detector)
        self._mark_dirty()
        self.detectors_changed.emit()

    def remove_detector(self, name: str) -> None:
        self._detectors = [d for d in self._detectors if d.name != name]
        self._mark_dirty()
        self.detectors_changed.emit()

    def rename_detector(self, old_name: str, new_name: str) -> None:
        for i, d in enumerate(self._detectors):
            if d.name == old_name:
                self._detectors[i] = Detector(
                    name=new_name,
                    position_xyz_mm=d.position_xyz_mm,
                    frame_axes=d.frame_axes,
                    kind=d.kind,
                )
                break
        self._mark_dirty()
        self.detectors_changed.emit()

    # -- scenario ------------------------------------------------------------

    def load_dose_curve(self, path: Path) -> None:
        self._load_dose_curve(path)
        self._mark_dirty()
        self.scenario_changed.emit()

    def _load_dose_curve(self, path: Path) -> None:
        from raysim.dose import build_dose_spline
        ddc = import_omere_dos(path)
        self._dose_spline = build_dose_spline(ddc)
        self._dose_curve_path = path

    def set_nside(self, nside: int) -> None:
        self._nside = nside
        self._mark_dirty()
        self.scenario_changed.emit()

    # -- run context ---------------------------------------------------------

    def build_run_context(self, output_path: Path | None = None) -> object:
        """Build a frozen RunContext for RunWorker with pre-computed hashes.

        Builds the Embree scene on first call (deferred from open_step to
        avoid blocking the UI with the full B1 pipeline during file open).
        """
        if self._gating is None or not self._gating.ready:
            raise RuntimeError("Cannot run: material assignments incomplete")
        if self._scene is None:
            self._rebuild_scene()
        if self._scene is None:
            detail = self._last_scene_error or "scene build failed"
            raise RuntimeError(f"Cannot run: {detail}")
        if self._dose_spline is None:
            raise RuntimeError("Cannot run: no dose curve loaded")

        from raysim.ui.workers.run_worker import RunContext

        geom_hash = hash_file(self._step_path) if self._step_path else ""
        mat_hash = hash_canonical([m.model_dump() for m in self._library.materials])
        assign_hash = hash_canonical([a.model_dump() for a in self._assignments])
        det_hash = hash_canonical([d.model_dump() for d in self._detectors])
        dose_hash = hash_file(self._dose_curve_path) if self._dose_curve_path else ""

        return RunContext(
            scene=self._scene,
            spline=self._dose_spline,
            detectors=list(self._detectors),
            nside=self._nside,
            emit_pixel_map=True,
            output_path=output_path,
            geometry_hash=geom_hash,
            materials_hash=mat_hash,
            assignments_hash=assign_hash,
            detectors_hash=det_hash,
            dose_curve_hash=dose_hash,
        )

    # -- gating --------------------------------------------------------------

    def _update_gating(self) -> None:
        if not self._leaves:
            self._gating = None
            self.gating_changed.emit()
            return
        solid_ids = [leaf.solid_id for leaf in self._leaves]
        self._gating = check_run_readiness(self._assignments, solid_ids, self._library)
        self.gating_changed.emit()

    # -- results -------------------------------------------------------------

    def set_detector_results(self, results: list[object]) -> None:
        self._detector_results = results
        self.run_complete.emit()

    # -- internal ------------------------------------------------------------

    def _mark_dirty(self) -> None:
        self._dirty = True
        self.project_changed.emit()
