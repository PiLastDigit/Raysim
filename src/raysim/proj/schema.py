"""Project schemas — Phase A.1.

Pydantic models for the inputs and outputs the headless ray engine consumes
and produces. The dose-depth-curve schema lives in ``raysim.env.schema``;
everything else lives here.

Stage A I/O contract (see MVP_STEPS §A.6 ``raysim run``):
  * Inputs: scene STL/OBJ, ``Material[]`` CSV/YAML, ``Detector[]`` JSON,
    ``DoseDepthCurve`` from ``raysim.env.importers.*``.
  * Output: ``RunResult`` JSON, canonicalized for byte-identity reproducibility
    on identical inputs (sorted keys, fixed float formatting; see
    ``raysim.proj.canonical_json``).

Field naming: never ``sigma`` or ``±σ``. The per-pixel statistic across the
HEALPix sphere is *angular spread* (a deterministic diagnostic of how much
shielding varies by direction), not a Monte Carlo σ. See MVP_STEPS §A.5.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

#: Bumped on every breaking change to the schemas defined here. v2 adds
#: ``Provenance.assignments_hash`` (Phase A: ``--assignments`` was changing
#: per-geom densities without leaving a provenance trace).
SCHEMA_VERSION = 2

# Frozen tuples for orientation matrices; Pydantic understands tuple typing for JSON round-trip.
Vec3 = tuple[float, float, float]
Frame3 = tuple[Vec3, Vec3, Vec3]

_DEFAULT_FRAME: Frame3 = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


class Material(BaseModel):
    """Material library entry — one per ``group_id``.

    MVP scope (see MVP_PLAN §3 "Material physics in MVP"): only ``density_g_cm3``
    drives the dose math. ``z_eff``, ``composition``, etc. are metadata only and
    are preserved for traceability + future Z-dependent corrections.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    group_id: str = Field(min_length=1)
    density_g_cm3: Annotated[float, Field(gt=0.0)]
    z_eff: float | None = None
    display_name: str = ""
    composition: dict[str, float] | None = None
    provenance: str = ""


class MaterialAssignment(BaseModel):
    """Maps a scene solid identifier to a library ``Material.group_id``.

    Stage A's STL convention (MVP_STEPS §A.3): ``solid_id`` is the STL filename
    stem (or OBJ group name). Stage B replaces this with the assembly tree path.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    solid_id: str = Field(min_length=1)
    material_group_id: str = Field(min_length=1)


class Detector(BaseModel):
    """Point or finite-box detector at a fixed scene-frame position.

    MVP sources are isotropic (a single mission-averaged DDC), so ``frame_axes``
    is cosmetic — but persisted from day 1 so post-MVP directional sources land
    without a schema bump (MVP_PLAN §3).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    position_xyz_mm: Vec3
    frame_axes: Frame3 = _DEFAULT_FRAME
    kind: Literal["point", "box"] = "point"
    box_extents_mm: Vec3 | None = None
    # Box → cloud-of-subdetectors approximation, see MVP_PLAN §4.9. MVP fixes
    # the cloud size; an explicit field is reserved for Stage B.
    box_n_subdetectors: int | None = None

    @model_validator(mode="after")
    def _check_box(self) -> Detector:
        if self.kind == "box":
            if self.box_extents_mm is None:
                raise ValueError("box detector requires box_extents_mm")
            if any(e <= 0 for e in self.box_extents_mm):
                raise ValueError("box_extents_mm must be strictly positive")
        else:
            if self.box_extents_mm is not None or self.box_n_subdetectors is not None:
                raise ValueError(
                    "box_extents_mm/box_n_subdetectors only valid when kind='box'"
                )
        return self


class Provenance(BaseModel):
    """Provenance block carried into every ``RunResult``.

    Bit-identical reproducibility (MVP_PLAN §1) requires the same: build SHA,
    pinned library versions, geometry hash, materials hash, **assignments
    hash**, detector hash, dose-curve hash, Nside, epsilon, seed. The
    assignments hash covers the ``MaterialAssignment[]`` mapping that decides
    which library material each scene solid resolves to — an empty mapping
    hashes to a stable canonical-empty value, so omitting ``--assignments`` is
    distinguishable from supplying an empty file. The receiving side
    reproduces ``run.json`` byte-for-byte from the same inputs.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = SCHEMA_VERSION
    raysim_version: str
    build_sha: str = ""  # filled by packaging when available; "" on dev runs
    library_versions: dict[str, str] = Field(default_factory=dict)
    nside: int
    epsilon_mm: float
    seed: int = 0
    bbox_diag_mm: float
    geometry_hash: str
    materials_hash: str
    assignments_hash: str
    detectors_hash: str
    dose_curve_hash: str


class ShieldingPercentiles(BaseModel):
    """Min / P05 / Median / P95 / Max of mm-Al-equivalent across HEALPix pixels."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    min: float
    p05: float
    median: float
    p95: float
    max: float


class DetectorResult(BaseModel):
    """Per-detector run output (mission-averaged, see MVP_PLAN §1)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    detector_name: str
    n_pixels: int

    # Mass-thickness and equivalent thickness, mean over HEALPix pixels.
    sigma_rho_l_mean_g_cm2: float
    mm_al_equivalent_mean: float

    # Total dose + per-species, krad(Si).
    dose_total_krad: float
    dose_per_species_krad: dict[str, float]

    # Diagnostic spread of *shielding* across directions — NOT a Monte Carlo σ.
    angular_spread_mm_al: float
    shielding_pctile_mm_al: ShieldingPercentiles

    # Run health counters (see A.4 termination invariants).
    n_overlap_suspicious_rays: int = 0
    n_stack_leak_rays: int = 0
    n_stack_mismatch_events: int = 0
    n_max_hit_rays: int = 0

    # Optional full HEALPix map of mm-Al-equivalent (per-pixel). Toggled by
    # ``--emit-pixel-map`` on the CLI; stored as a tuple for canonical JSON.
    healpix_mm_al_per_pixel: tuple[float, ...] | None = None


class RunResult(BaseModel):
    """Top-level run output. Canonical JSON of this is the deterministic
    artifact (MVP_PLAN §1, MVP_STEPS §A.6)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = SCHEMA_VERSION
    detectors: tuple[DetectorResult, ...]
    provenance: Provenance
