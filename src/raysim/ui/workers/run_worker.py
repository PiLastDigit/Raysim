"""QThread engine dispatcher — Phase B3.

Wraps the Stage A per-detector aggregation loop in a ``QThread`` so the UI
stays responsive.  Emits progress signals per detector and a final result.

``RunContext`` is a frozen dataclass carrying all inputs + pre-computed
provenance hashes.  The GUI builds bit-identical provenance to the CLI.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, Signal

from raysim import __version__
from raysim.dose.aggregator import aggregate_detector
from raysim.proj.schema import (
    Detector,
    DetectorResult,
    Provenance,
    RunResult,
)

if TYPE_CHECKING:
    from raysim.dose.spline import DoseSpline
    from raysim.ray.scene import BuiltScene

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


@dataclass(frozen=True)
class RunContext:
    """All inputs needed for a run, with pre-computed provenance hashes."""

    scene: BuiltScene
    spline: DoseSpline
    detectors: list[Detector]
    nside: int
    emit_pixel_map: bool
    output_path: Path | None
    geometry_hash: str
    materials_hash: str
    assignments_hash: str
    detectors_hash: str
    dose_curve_hash: str
    human_metadata_path: Path | None = None
    overlap_validated: bool = False
    overlap_summary: dict[str, int] | None = None


class RunWorker(QThread):  # type: ignore[misc]
    """Runs the per-detector aggregation loop in a background thread."""

    detector_done = Signal(int, object)
    run_complete = Signal(object)
    run_error = Signal(str)

    def __init__(self, context: RunContext, parent: object | None = None) -> None:
        super().__init__(parent)
        self._ctx = context

    def run(self) -> None:
        try:
            results: list[DetectorResult] = []
            for i, detector in enumerate(self._ctx.detectors):
                if self.isInterruptionRequested():
                    self.run_error.emit("Run cancelled by user")
                    return

                res = aggregate_detector(
                    self._ctx.scene,
                    self._ctx.spline,
                    detector,
                    nside=self._ctx.nside,
                    emit_pixel_map=self._ctx.emit_pixel_map,
                )
                results.append(res)
                self.detector_done.emit(i, res)

            epsilon_mm = 1e-6 * self._ctx.scene.bbox_diag_mm
            provenance = Provenance(
                raysim_version=__version__,
                library_versions=_library_versions(),
                nside=self._ctx.nside,
                epsilon_mm=epsilon_mm,
                bbox_diag_mm=self._ctx.scene.bbox_diag_mm,
                geometry_hash=self._ctx.geometry_hash,
                materials_hash=self._ctx.materials_hash,
                assignments_hash=self._ctx.assignments_hash,
                detectors_hash=self._ctx.detectors_hash,
                dose_curve_hash=self._ctx.dose_curve_hash,
            )

            n_max_hit = sum(r.n_max_hit_rays for r in results)
            if n_max_hit:
                self.run_error.emit(
                    f"{n_max_hit} ray(s) exceeded the per-ray hit safety cap. "
                    "Run is fatal — check geometry for leaks."
                )
                return

            run_result = RunResult(
                detectors=tuple(results),
                provenance=provenance,
            )

            if self._ctx.output_path is not None:
                from raysim.proj.canonical_json import dumps as canonical_dumps
                self._ctx.output_path.parent.mkdir(parents=True, exist_ok=True)
                self._ctx.output_path.write_text(
                    canonical_dumps(run_result), encoding="utf-8",
                )

            human_path = self._ctx.human_metadata_path
            if human_path is None and self._ctx.output_path is not None:
                human_path = self._ctx.output_path.with_suffix(".human.json")
            if human_path is not None:
                import json
                from datetime import UTC, datetime

                human_meta: dict[str, object] = {
                    "timestamp_utc": datetime.now(tz=UTC).isoformat(),
                    "raysim_version": __version__,
                    "overlap_validation": "validated" if self._ctx.overlap_validated else "skipped",
                }
                if self._ctx.overlap_summary is not None:
                    human_meta["overlap_report_summary"] = self._ctx.overlap_summary
                human_path.write_text(
                    json.dumps(human_meta, indent=2), encoding="utf-8",
                )

            self.run_complete.emit(run_result)

        except Exception as exc:
            self.run_error.emit(str(exc))
