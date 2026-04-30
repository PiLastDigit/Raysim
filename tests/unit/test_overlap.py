"""Phase B1.5: overlap diagnostic — 4-way classification, tied pairing."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("OCC.Core")

from raysim.geom.healing import heal_assembly
from raysim.geom.overlap import OverlapStatus, diagnose_overlaps
from raysim.geom.step_loader import iter_leaves, load_step
from raysim.geom.tessellation import tessellate

ROOT = Path(__file__).resolve().parents[2]
STEP_DIR = ROOT / "benchmarks" / "step"


def _pipeline(step_file: str) -> tuple:
    node = load_step(STEP_DIR / step_file)
    leaves = list(iter_leaves(node))
    tess = [tessellate(leaf) for leaf in leaves]
    healed = list(heal_assembly(tess))
    shapes = {leaf.solid_id: leaf.shape for leaf in leaves}
    return healed, shapes


@pytest.mark.needs_occt
def test_single_solid_no_overlaps() -> None:
    healed, shapes = _pipeline("aluminum_box.step")
    report = diagnose_overlaps(healed, shapes=shapes)
    assert len(report.pairs) == 0
    assert len(report.mismatched_contacts) == 0


@pytest.mark.needs_occt
def test_concentric_shell_classified() -> None:
    healed, shapes = _pipeline("concentric_shell.step")
    report = diagnose_overlaps(healed, shapes=shapes)
    assert len(report.pairs) >= 1
    for p in report.pairs:
        assert p.status in (OverlapStatus.CONTACT_ONLY, OverlapStatus.ACCEPTED_NESTED)


@pytest.mark.needs_occt
def test_nested_pin_accepted_nested() -> None:
    healed, shapes = _pipeline("nested_pin.step")
    report = diagnose_overlaps(healed, shapes=shapes)
    nested = [p for p in report.pairs if p.status == OverlapStatus.ACCEPTED_NESTED]
    assert len(nested) >= 1


@pytest.mark.needs_occt
def test_interference_small_warning() -> None:
    healed, shapes = _pipeline("interference_partial_small.step")
    report = diagnose_overlaps(healed, shapes=shapes)
    assert len(report.pairs) >= 1
    statuses = {p.status for p in report.pairs}
    assert OverlapStatus.INTERFERENCE_WARNING in statuses or OverlapStatus.INTERFERENCE_FAIL in statuses


@pytest.mark.needs_occt
def test_interference_large_fail() -> None:
    healed, shapes = _pipeline("interference_partial_large.step")
    report = diagnose_overlaps(healed, shapes=shapes)
    fails = report.failed()
    assert len(fails) >= 1


@pytest.mark.needs_occt
def test_coincident_faces_tied_pairs() -> None:
    """Topology-shared faces produce vertex-match tied pairs."""
    healed, shapes = _pipeline("coincident_faces.step")
    report = diagnose_overlaps(healed, shapes=shapes)
    all_tied = report.all_tied_triangle_pairs()
    assert len(all_tied) > 0


@pytest.mark.needs_occt
def test_coincident_faces_mismatched_warning() -> None:
    """Separately tessellated coplanar faces trigger MismatchedContactRegion."""
    healed, shapes = _pipeline("coincident_faces_mismatched.step")
    report = diagnose_overlaps(healed, shapes=shapes)
    assert len(report.mismatched_contacts) >= 1
    mcr = report.mismatched_contacts[0]
    assert mcr.matched_area_fraction < 0.5


@pytest.mark.needs_occt
def test_coincident_faces_partial_coverage() -> None:
    """Partial coplanar contact: some pairs + a MismatchedContactRegion."""
    healed, shapes = _pipeline("coincident_faces_partial.step")
    report = diagnose_overlaps(healed, shapes=shapes)
    assert len(report.mismatched_contacts) >= 1
