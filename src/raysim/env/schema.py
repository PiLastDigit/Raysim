"""Canonical internal dose-depth-curve (DDC) schema — see MVP_PLAN.md §3.

This is the *only* environment input RaySim consumes in MVP. Importers in
``raysim.env.importers.*`` produce instances of this schema; the dose module
consumes them. Adding a new dialect (SPENVIS, IRENE, etc.) is one importer file
plus a fixture, with no downstream changes.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Canonical species names. RaySim normalizes incoming dialects (OMERE, SPENVIS, ...)
# to this set so the dose module + reports have a stable contract. Other dialects
# may carry richer per-species detail in `extra_species` for traceability.
CANONICAL_SPECIES = ("trapped_electron", "trapped_proton", "solar_proton", "gamma")


class DoseDepthCurve(BaseModel):
    """Solid-sphere dose-depth curve, mission-averaged.

    Attributes
    ----------
    thickness_mm_al :
        Monotonically increasing 1-D array, mm Al-equivalent.
    dose_per_species :
        Dict ``{canonical_species_name → 1-D array}``, krad(Si) at each thickness sample.
        Missing canonical species default to all-zeros (e.g. gamma may be absent).
    dose_total :
        1-D array, krad(Si) per thickness sample. Equals the sum over all species
        present in the source file (i.e. ``dose_per_species`` *plus* anything in
        ``extra_species`` that the source attributes to the total).
    extra_species :
        Per-species columns the dialect carried that don't map to a canonical name
        (e.g. OMERE's ``other_electrons``, ``other_protons``, ``other_gamma``).
        Preserved verbatim for traceability and for the report's per-species table.
    source_tool :
        Free-text provenance (``"OMERE-5.9.3.41295"`` etc.). Untrusted; carried
        through verbatim.
    mission_metadata :
        Dict of dialect-specific provenance carried into the report unchanged
        (orbit, model versions, percentiles, lifetime, ...). Untrusted; not parsed
        by the dose module.
    schema_version :
        Bumped on any breaking change.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    schema_version: int = Field(default=1, frozen=True)
    thickness_mm_al: tuple[float, ...]
    dose_per_species: dict[str, tuple[float, ...]]
    dose_total: tuple[float, ...]
    extra_species: dict[str, tuple[float, ...]] = Field(default_factory=dict)
    source_tool: str = ""
    mission_metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_shapes(self) -> DoseDepthCurve:
        n = len(self.thickness_mm_al)
        if n < 2:
            raise ValueError("DDC needs at least two thickness samples")
        if any(
            self.thickness_mm_al[i + 1] <= self.thickness_mm_al[i]
            for i in range(n - 1)
        ):
            raise ValueError("thickness_mm_al must be strictly increasing")
        if any(t < 0 for t in self.thickness_mm_al):
            raise ValueError("thickness_mm_al must be non-negative")
        if len(self.dose_total) != n:
            raise ValueError(
                f"dose_total length {len(self.dose_total)} != thickness length {n}"
            )
        for name, col in self.dose_per_species.items():
            if name not in CANONICAL_SPECIES:
                raise ValueError(
                    f"dose_per_species key {name!r} not in canonical species "
                    f"{CANONICAL_SPECIES}; use extra_species for non-canonical columns"
                )
            if len(col) != n:
                raise ValueError(
                    f"species {name!r} length {len(col)} != thickness length {n}"
                )
        for name, col in self.extra_species.items():
            if len(col) != n:
                raise ValueError(
                    f"extra_species {name!r} length {len(col)} != thickness length {n}"
                )
        return self
