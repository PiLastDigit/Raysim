"""Run gating and density anomaly warnings — Phase B2.6.

Pure functions that check whether a run is permitted and flag density
outliers. Callable from CLI and future UI.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from raysim.mat.library import MaterialLibrary
from raysim.proj.schema import Material, MaterialAssignment


@dataclass(frozen=True)
class GatingResult:
    """Result of a run-readiness check."""

    ready: bool
    missing_solids: tuple[str, ...]
    unresolved_assignments: tuple[str, ...]


@dataclass(frozen=True)
class DensityAnomaly:
    """A density value outside the expected range."""

    group_id: str
    density_g_cm3: float
    kind: Literal["low", "high"]


def check_run_readiness(
    assignments: Sequence[MaterialAssignment],
    solids: Sequence[str],
    library: MaterialLibrary,
) -> GatingResult:
    """Verify every solid has an assignment that resolves to a library entry."""
    assigned: dict[str, str] = {a.solid_id: a.material_group_id for a in assignments}

    missing: list[str] = []
    unresolved: list[str] = []

    for sid in solids:
        if sid not in assigned:
            missing.append(sid)
        elif assigned[sid] not in library:
            unresolved.append(sid)

    return GatingResult(
        ready=not missing and not unresolved,
        missing_solids=tuple(missing),
        unresolved_assignments=tuple(unresolved),
    )


_LOW_DENSITY_THRESHOLD = 0.5
_HIGH_DENSITY_THRESHOLD = 25.0


def check_density_anomalies(
    materials: Sequence[Material],
) -> list[DensityAnomaly]:
    """Flag materials with density outside [0.5, 25.0] g/cm³."""
    anomalies: list[DensityAnomaly] = []
    for m in materials:
        if m.density_g_cm3 < _LOW_DENSITY_THRESHOLD:
            anomalies.append(DensityAnomaly(
                group_id=m.group_id,
                density_g_cm3=m.density_g_cm3,
                kind="low",
            ))
        elif m.density_g_cm3 > _HIGH_DENSITY_THRESHOLD:
            anomalies.append(DensityAnomaly(
                group_id=m.group_id,
                density_g_cm3=m.density_g_cm3,
                kind="high",
            ))
    return anomalies
