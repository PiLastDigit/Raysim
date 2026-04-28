"""Phase 0 §0.4: benchmark corpus is generated, hashes are stable, analytic
targets are internally consistent, *and* the YAML target chords actually match
the STL geometry when ray-traced. The last check is the geometry/YAML coupling
guard — if either drifts, this test fails before A.7 ever runs.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import trimesh
import yaml

REPO = Path(__file__).resolve().parent.parent.parent
GEOM = REPO / "benchmarks" / "geometries"
ASM = REPO / "benchmarks" / "assemblies"
TARGETS = REPO / "benchmarks" / "analytic_targets.yaml"

# Mapping from geometry name → {material → stl path relative to repo root}.
# The custom test article lives under assemblies/, the rest under geometries/.
GEOMETRY_STL_PATHS = {
    "aluminum_box": {"aluminum": "benchmarks/geometries/aluminum_box/aluminum.stl"},
    "solid_sphere": {"aluminum": "benchmarks/geometries/solid_sphere/aluminum.stl"},
    "concentric_shell": {
        "aluminum": "benchmarks/geometries/concentric_shell/aluminum.stl",
        "copper": "benchmarks/geometries/concentric_shell/copper.stl",
    },
    "custom_test_article": {
        "aluminum": "benchmarks/assemblies/custom_test_article/aluminum.stl",
        "fr4": "benchmarks/assemblies/custom_test_article/fr4.stl",
        "copper": "benchmarks/assemblies/custom_test_article/copper.stl",
        "gaas": "benchmarks/assemblies/custom_test_article/gaas.stl",
    },
}


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    "subdir",
    [
        GEOM / "aluminum_box",
        GEOM / "solid_sphere",
        GEOM / "concentric_shell",
        ASM / "custom_test_article",
    ],
)
def test_geometry_dir_has_manifest(subdir: Path) -> None:
    assert subdir.exists(), f"missing {subdir} — run scripts/build_benchmarks.py"
    manifest = subdir / "manifest.json"
    assert manifest.exists()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["files"], f"empty manifest for {subdir}"
    for info in data["files"].values():
        stl = REPO / info["path"]
        assert stl.exists(), f"missing STL referenced by {manifest}: {stl}"
        assert _sha256(stl) == info["sha256"], (
            f"hash drift in {stl} — re-run scripts/build_benchmarks.py and commit"
        )


def test_analytic_targets_loadable() -> None:
    data = yaml.safe_load(TARGETS.read_text(encoding="utf-8"))
    assert "geometries" in data
    assert "aluminum_box" in data["geometries"]
    assert "solid_sphere" in data["geometries"]
    assert "concentric_shell" in data["geometries"]


def test_analytic_targets_internally_consistent() -> None:
    """∑ρL listed in the YAML matches sum(chord_mm/10 × ρ_g_cm3) over species."""
    data = yaml.safe_load(TARGETS.read_text(encoding="utf-8"))
    densities = data["defaults"]["densities_g_cm3"]
    for gname, gdata in data["geometries"].items():
        for ray in gdata.get("rays", []):
            expected = sum(
                (chord / 10.0) * densities[mat]
                for mat, chord in ray["chord_lengths_mm"].items()
            )
            # tolerate the 1% level — YAML uses rounded reference values
            assert abs(ray["sigma_rho_l_g_cm2"] - expected) < 0.5, (
                f"{gname} ray {ray['origin']} ∑ρL {ray['sigma_rho_l_g_cm2']} ≠ "
                f"computed {expected:.3f}"
            )


def _per_material_chord(mesh: trimesh.Trimesh, origin: np.ndarray, direction: np.ndarray) -> float:
    """Sum of (exit_t − entry_t) pairs for a ray cast through one material's mesh.

    Assumes the mesh is a closed surface (or set of closed sub-shells) so hit
    counts are even and consecutive sorted hits pair into entry/exit.
    """
    locs, _, _ = mesh.ray.intersects_location(
        ray_origins=[origin], ray_directions=[direction]
    )
    if len(locs) == 0:
        return 0.0
    ts = sorted(float(np.linalg.norm(loc - origin)) for loc in locs)
    if len(ts) % 2 != 0:
        raise AssertionError(
            f"odd hit count {len(ts)} — mesh is not a watertight closed surface"
        )
    return sum(ts[i + 1] - ts[i] for i in range(0, len(ts), 2))


def _geometry_ray_cases() -> list[tuple[str, dict[str, object]]]:
    """Flatten YAML into one (geometry_name, ray) tuple per ray for parametrize."""
    data = yaml.safe_load(TARGETS.read_text(encoding="utf-8"))
    cases: list[tuple[str, dict[str, object]]] = []
    for gname, gdata in data["geometries"].items():
        for ray in gdata.get("rays", []):
            cases.append((gname, ray))
    return cases


@pytest.mark.parametrize(("gname", "ray"), _geometry_ray_cases())
def test_yaml_chord_matches_stl_geometry(gname: str, ray: dict[str, object]) -> None:
    """Cast each YAML ray through the actual STL via trimesh's ray engine; the
    per-material chord lengths must match the YAML targets to ≤1e-5.

    This is the geometry/YAML coupling guard: if ``build_benchmarks.py`` drifts
    from ``analytic_targets.yaml`` (or vice-versa), the Phase A acceptance suite
    would silently validate the wrong geometry. This test fails first instead.
    """
    origin = np.asarray(ray["origin"], dtype=float)
    direction = np.asarray(ray["direction"], dtype=float)
    expected_chords: dict[str, float] = ray["chord_lengths_mm"]  # type: ignore[assignment]

    for material, expected in expected_chords.items():
        stl = REPO / GEOMETRY_STL_PATHS[gname][material]
        mesh = trimesh.load(stl)
        actual = _per_material_chord(mesh, origin, direction)
        if expected == 0.0:
            assert actual == pytest.approx(0.0, abs=1e-9), (
                f"{gname}/{material}: expected miss, got chord {actual} mm"
            )
        else:
            rel = abs(actual - expected) / expected
            assert rel < 1e-5, (
                f"{gname}/{material}: STL chord {actual:.6f} mm vs YAML "
                f"{expected:.6f} mm (rel err {rel:.2e})"
            )
