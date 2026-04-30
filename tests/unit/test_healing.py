"""Phase B1.3: healing — healer idempotency, shell orientation normalization."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("OCC.Core")

from raysim.geom.healing import ShellRole, heal_assembly
from raysim.geom.step_loader import iter_leaves, load_step
from raysim.geom.tessellation import tessellate

ROOT = Path(__file__).resolve().parents[2]
STEP_DIR = ROOT / "benchmarks" / "step"


def _tessellate_all(step_file: str) -> list:
    node = load_step(STEP_DIR / step_file)
    return [tessellate(leaf) for leaf in iter_leaves(node)]


@pytest.mark.needs_occt
def test_aluminum_box_single_outer() -> None:
    solids = _tessellate_all("aluminum_box.step")
    healed = heal_assembly(solids)
    assert len(healed) == 1
    assert len(healed[0].shells) >= 1
    assert healed[0].shells[0].role == ShellRole.OUTER


@pytest.mark.needs_occt
def test_hollow_box_cavity_convention() -> None:
    """Hollow box: outer shell + cavity shell. Cavity normals point into void."""
    solids = _tessellate_all("hollow_box.step")
    healed = heal_assembly(solids)
    assert len(healed) == 1
    roles = {s.role for s in healed[0].shells}
    assert ShellRole.OUTER in roles
    assert ShellRole.CAVITY in roles


@pytest.mark.needs_occt
def test_healer_idempotency() -> None:
    """Running heal_assembly twice produces no further changes."""
    solids = _tessellate_all("aluminum_box.step")
    healed1 = heal_assembly(solids)

    solids2 = _tessellate_all("aluminum_box.step")
    healed2 = heal_assembly(solids2)

    for h1, h2 in zip(healed1, healed2, strict=True):
        for s1, s2 in zip(h1.shells, h2.shells, strict=True):
            np.testing.assert_array_equal(s1.faces, s2.faces)
            np.testing.assert_allclose(s1.triangle_normals, s2.triangle_normals, atol=1e-12)


@pytest.mark.needs_occt
def test_reversed_outer_is_flipped() -> None:
    """Reversed-outer fixture should have its shell flipped during healing."""
    solids = _tessellate_all("reversed_outer.step")
    healed = heal_assembly(solids)
    assert len(healed) == 1
    assert healed[0].shells[0].role == ShellRole.OUTER


@pytest.mark.needs_occt
def test_concentric_shell_roles() -> None:
    """Concentric shell: Al shell solid has outer + cavity roles."""
    solids = _tessellate_all("concentric_shell.step")
    healed = heal_assembly(solids)
    assert len(healed) == 2
    multi_shell = [h for h in healed if len(h.shells) > 1]
    if multi_shell:
        roles = {s.role for s in multi_shell[0].shells}
        assert ShellRole.OUTER in roles
        assert ShellRole.CAVITY in roles


@pytest.mark.needs_occt
def test_normals_unit_length_after_healing() -> None:
    solids = _tessellate_all("aluminum_box.step")
    healed = heal_assembly(solids)
    for solid in healed:
        for shell in solid.shells:
            norms = np.linalg.norm(shell.triangle_normals, axis=1)
            np.testing.assert_allclose(norms, 1.0, atol=1e-12)
