"""Geometry pipeline orchestrator — Phase B1.6.

Glues ``load_step`` → ``tessellate`` → ``heal_assembly`` →
``validate_watertightness`` → ``diagnose_overlaps`` into a single call
returning a ``ValidatedAssembly``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import structlog

from raysim.geom.healing import HealedSolid, heal_assembly
from raysim.geom.overlap import OverlapReport, diagnose_overlaps
from raysim.geom.step_loader import iter_leaves, load_step
from raysim.geom.tessellation import tessellate
from raysim.geom.watertightness import WatertightnessReport, validate_watertightness

_LOG = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ValidationOverrides:
    """Records which safety gates the caller bypassed."""

    accept_warnings: bool = False
    accept_interference_fail: bool = False
    accept_watertightness_failures: bool = False


@dataclass(frozen=True)
class ValidatedAssembly:
    """Result of the full geometry pipeline."""

    step_path: Path | None
    linear_mm: float
    angular_rad: float
    solids: tuple[HealedSolid, ...]
    watertightness: WatertightnessReport
    overlaps: OverlapReport
    overrides_used: ValidationOverrides = field(default_factory=ValidationOverrides)


def build_assembly_from_step(
    step_path: str | Path,
    *,
    linear_mm: float = 0.1,
    angular_rad: float = 0.5,
) -> ValidatedAssembly:
    """Load a STEP file through the full B1 pipeline.

    Returns ``ValidatedAssembly`` with ``overrides_used`` all-False.
    The adapter mutates a copy with the actual override flags.
    """
    step_path = Path(step_path)
    _LOG.info("pipeline.start", step_path=str(step_path))

    # B1.1: Load STEP.
    root = load_step(step_path)
    leaves = list(iter_leaves(root))

    # B1.2: Tessellate each leaf.
    tessellated = [tessellate(leaf, linear_mm=linear_mm, angular_rad=angular_rad)
                   for leaf in leaves]

    # B1.3: Heal + normalize orientations.
    healed = heal_assembly(tessellated)

    # B1.4: Watertightness validation.
    wt_report = validate_watertightness(healed)

    # B1.5: Overlap diagnostic (pass original shapes for volume classification).
    shape_map = {leaf.solid_id: leaf.shape for leaf in leaves}
    overlap_report = diagnose_overlaps(healed, shapes=shape_map)

    _LOG.info(
        "pipeline.done",
        n_solids=len(healed),
        watertight=wt_report.is_watertight(),
        n_overlap_pairs=len(overlap_report.pairs),
    )

    return ValidatedAssembly(
        step_path=step_path,
        linear_mm=linear_mm,
        angular_rad=angular_rad,
        solids=healed,
        watertightness=wt_report,
        overlaps=overlap_report,
    )
