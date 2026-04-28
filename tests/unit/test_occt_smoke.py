"""Phase 0 smoke (§0.2): pythonocc-core minimal STEP + tessellation flow.

Skipped automatically when ``OCC.Core`` is not importable (it is conda-only,
not on PyPI). When present, verifies the three exact OCCT classes Phase B1
depends on:

  * ``BRepPrimAPI_MakeBox`` — fixture geometry
  * ``BRepMesh_IncrementalMesh`` — tessellation (B1.2)
  * ``BRepMesh_ModelHealer`` — healing (B1.3); §0.2 flagged this as version-sensitive

A separate XFAIL records the conda-forge 7.9.0 ``XCAFDoc_DocumentTool``
``Standard_NullObject`` bootstrap failure documented in
docs/decisions/phase-0.md — that path is not on the Phase 0 gate but is needed
for B2.2.
"""

from __future__ import annotations

import pytest

OCC = pytest.importorskip("OCC.Core")


@pytest.mark.needs_occt
def test_makebox_brepmesh_modelhealer() -> None:
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh, BRepMesh_ModelHealer
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox

    cube = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
    mesh = BRepMesh_IncrementalMesh(cube, 0.1, False, 0.5, True)
    mesh.Perform()
    assert mesh.IsDone()
    # ModelHealer is the §0.2 binding-gap risk; just verify it's importable + callable.
    assert BRepMesh_ModelHealer is not None


@pytest.mark.needs_occt
def test_step_writer_reader_roundtrip(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Reader, STEPControl_Writer

    cube = BRepPrimAPI_MakeBox(10.0, 10.0, 10.0).Shape()
    path = tmp_path / "cube.step"
    w = STEPControl_Writer()
    w.Transfer(cube, STEPControl_AsIs)
    w.Write(str(path))
    assert path.exists()
    r = STEPControl_Reader()
    assert r.ReadFile(str(path)) == IFSelect_RetDone
    r.TransferRoots()
    assert r.OneShape() is not None


@pytest.mark.needs_occt
@pytest.mark.xfail(
    reason=(
        "conda-forge pythonocc-core 7.9.0: TDocStd_Document construction throws "
        "Standard_NullObject. Documented in docs/decisions/phase-0.md; affects B1.1 / B2.2 "
        "STEP material-tag ingestion only, not Phase A."
    ),
    strict=False,
    raises=Exception,
)
def test_xcafdoc_material_tool_bootstrap() -> None:
    from OCC.Core.BinXCAFDrivers import binxcafdrivers
    from OCC.Core.TCollection import TCollection_ExtendedString
    from OCC.Core.TDocStd import TDocStd_Document
    from OCC.Core.XCAFApp import XCAFApp_Application
    from OCC.Core.XCAFDoc import XCAFDoc_DocumentTool

    app = XCAFApp_Application.GetApplication()
    binxcafdrivers.DefineFormat(app)
    doc = TDocStd_Document(TCollection_ExtendedString("BinXCAF"))
    mat = XCAFDoc_DocumentTool.MaterialTool(doc.Main())
    assert mat is not None
