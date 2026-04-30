"""Project file schema and I/O — Phase B2.5.

The ``.raysim`` project file is a Pydantic model serialized via canonical
JSON. Bit-stable on save/reopen/save: ``created_at_utc`` is set once at
creation and preserved verbatim on subsequent cycles.
"""

from __future__ import annotations

import json
from pathlib import Path

import structlog
from pydantic import BaseModel, ConfigDict, Field

from raysim.proj.canonical_json import dumps as canonical_dumps
from raysim.proj.hashing import hash_file
from raysim.proj.schema import Detector, MaterialAssignment

_LOG = structlog.get_logger(__name__)

PROJECT_SCHEMA_VERSION = 1


class NamingRuleOverride(BaseModel):
    """A project-level naming-rule override."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pattern: str = Field(min_length=1)
    group_id: str = Field(min_length=1)
    priority: int = 10


class GeometryRef(BaseModel):
    """Reference to the source geometry file."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    tessellation_linear_mm: float = 0.1
    tessellation_angular_rad: float = 0.5


class ProjectFile(BaseModel):
    """The ``.raysim`` project file."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_schema_version: int = PROJECT_SCHEMA_VERSION

    geometry: GeometryRef
    materials_library_path: str | None = None
    materials_library_sha256: str | None = None

    assignments: tuple[MaterialAssignment, ...] = ()
    assignment_sources: dict[str, str] = Field(default_factory=dict)

    naming_rule_overrides: tuple[NamingRuleOverride, ...] | None = None

    detectors: tuple[Detector, ...] = ()

    dose_curve_path: str | None = None
    dose_curve_sha256: str | None = None

    interference_overrides: dict[str, str] = Field(default_factory=dict)

    created_at_utc: str = ""
    raysim_version: str = ""


def save_project(project: ProjectFile, path: Path) -> None:
    """Write a ``.raysim`` project file as canonical JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_dumps(project), encoding="utf-8")


def load_project(path: Path) -> ProjectFile:
    """Read and validate a ``.raysim`` project file.

    Accepts ``project_schema_version`` equal to ``PROJECT_SCHEMA_VERSION``
    or ``PROJECT_SCHEMA_VERSION - 1`` (with migration). Verifies the
    geometry hash on load and warns if stale.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))

    file_version = raw.get("project_schema_version", 0)
    if file_version == PROJECT_SCHEMA_VERSION:
        pass
    elif file_version == PROJECT_SCHEMA_VERSION - 1:
        raw = _migrate(raw, file_version, PROJECT_SCHEMA_VERSION)
    else:
        raise ValueError(
            f"Unsupported project schema version {file_version}; "
            f"expected {PROJECT_SCHEMA_VERSION} or {PROJECT_SCHEMA_VERSION - 1}"
        )

    project = ProjectFile.model_validate(raw)

    _verify_geometry_hash(project, path.parent)

    return project


def geometry_hash(project: ProjectFile, base_dir: Path) -> str:
    """Compute SHA-256 of the geometry file referenced by the project."""
    geom_path = base_dir / project.geometry.path
    return hash_file(geom_path)


def _verify_geometry_hash(project: ProjectFile, base_dir: Path) -> None:
    """Warn if the stored geometry hash doesn't match the file on disk."""
    geom_path = base_dir / project.geometry.path
    if not geom_path.exists():
        _LOG.warning(
            "project.geometry_not_found",
            path=str(geom_path),
        )
        return
    actual = hash_file(geom_path)
    if actual != project.geometry.sha256:
        _LOG.warning(
            "project.geometry_hash_mismatch",
            expected=project.geometry.sha256[:16] + "...",
            actual=actual[:16] + "...",
            path=str(geom_path),
        )


def _migrate(raw: dict[str, object], from_v: int, to_v: int) -> dict[str, object]:
    """Migrate a project file from *from_v* to *to_v*."""
    _LOG.info("project.migrating", from_version=from_v, to_version=to_v)
    raw["project_schema_version"] = to_v
    return raw
