"""Material library — Phase B2.1.

Loads a seeded or user-supplied YAML material library and exposes it as a
``MaterialLibrary`` lookup keyed by ``group_id``.
"""

from __future__ import annotations

import importlib.resources
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml

from raysim.proj.schema import Material


def _default_library_path() -> Path:
    """Return the path to the bundled default library YAML."""
    ref = importlib.resources.files("raysim.mat").joinpath("default_library.yaml")
    with importlib.resources.as_file(ref) as p:
        return Path(p)


@dataclass(frozen=True)
class MaterialLibrary:
    """Frozen collection of ``Material`` entries, indexed by ``group_id``."""

    materials: tuple[Material, ...]
    by_group_id: dict[str, Material]

    def __contains__(self, group_id: str) -> bool:
        return group_id in self.by_group_id

    def __getitem__(self, group_id: str) -> Material:
        return self.by_group_id[group_id]

    def __len__(self) -> int:
        return len(self.materials)

    def merge(self, other: MaterialLibrary) -> MaterialLibrary:
        """Return a new library with *other*'s entries added (or overriding)."""
        merged = dict(self.by_group_id)
        merged.update(other.by_group_id)
        return _build_library(tuple(merged.values()))


def _build_library(materials: Sequence[Material]) -> MaterialLibrary:
    by_id: dict[str, Material] = {}
    for m in materials:
        if m.group_id in by_id:
            raise ValueError(f"Duplicate group_id in material library: {m.group_id!r}")
        by_id[m.group_id] = m
    return MaterialLibrary(materials=tuple(materials), by_group_id=by_id)


def load_library(path: Path | None = None) -> MaterialLibrary:
    """Load a material library from *path* (YAML), or the bundled default."""
    if path is None:
        path = _default_library_path()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries = data["materials"] if isinstance(data, dict) and "materials" in data else data
    materials = [Material.model_validate(e) for e in entries]
    return _build_library(materials)
