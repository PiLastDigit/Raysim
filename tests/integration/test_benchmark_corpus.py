"""Phase 0 §0.4: benchmark corpus is generated, hashes are stable, analytic
targets are internally consistent."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent.parent
GEOM = REPO / "benchmarks" / "geometries"
ASM = REPO / "benchmarks" / "assemblies"
TARGETS = REPO / "benchmarks" / "analytic_targets.yaml"


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
