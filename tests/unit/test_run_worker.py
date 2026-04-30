"""Tests for raysim.ui.workers.run_worker — Phase B3.

Tests that don't need Qt use plain pytest.  RunContext construction and
provenance hash completeness are the primary concerns.

PySide6 is required at module import level by run_worker (for QThread).
"""

from __future__ import annotations

from dataclasses import fields

import pytest

pytest.importorskip("PySide6")


def test_run_context_fields() -> None:
    """RunContext carries all required fields for provenance."""
    from raysim.ui.workers.run_worker import RunContext

    field_names = {f.name for f in fields(RunContext)}
    assert "scene" in field_names
    assert "spline" in field_names
    assert "detectors" in field_names
    assert "nside" in field_names
    assert "emit_pixel_map" in field_names
    assert "output_path" in field_names
    assert "geometry_hash" in field_names
    assert "materials_hash" in field_names
    assert "assignments_hash" in field_names
    assert "detectors_hash" in field_names
    assert "dose_curve_hash" in field_names


def test_run_context_is_frozen() -> None:
    """RunContext should be a frozen dataclass."""
    from raysim.ui.workers.run_worker import RunContext

    ctx = RunContext(
        scene=None,  # type: ignore[arg-type]
        spline=None,  # type: ignore[arg-type]
        detectors=[],
        nside=64,
        emit_pixel_map=False,
        output_path=None,
        geometry_hash="a" * 64,
        materials_hash="b" * 64,
        assignments_hash="c" * 64,
        detectors_hash="d" * 64,
        dose_curve_hash="e" * 64,
    )
    with pytest.raises(AttributeError):
        ctx.nside = 128  # type: ignore[misc]


def test_library_versions_returns_dict() -> None:
    """_library_versions returns a dict of installed package versions."""
    from raysim.ui.workers.run_worker import _library_versions

    versions = _library_versions()
    assert isinstance(versions, dict)
    assert "numpy" in versions
