# B3 Windows Testing — Status and Open Issues

**Date**: 2026-05-01
**Context**: Phase B3 UI implementation landed, first Windows GUI testing session.

## What works

- **GUI launches** from desktop shortcut (`pythonw.exe`) and CLI (`.\raysim.cmd gui`)
- **PySide6 panels** all render: assembly tree, materials, detectors, scenario, run, results
- **STEP file loading** — 3994-solid assembly loads in seconds (deferred pipeline)
- **XCAF reader no longer crashes** — applied workaround from pythonocc-core issue #1428: replaced `TDocStd_Document(TCollection_ExtendedString("XDE"))` with `TDocStd_Application` + `binxcafdrivers.DefineFormat` + `app.NewDocument("BinXCAF", doc)`
- **Material library** displays all 14 seeded entries
- **Auto-assignment status** shows correctly (Auto-matched: 0, Ambiguous: 0, Unassigned: N)
- **Install script** (`scripts/install-windows.ps1`) handles micromamba download, env creation, editable install, launcher generation, desktop shortcut
- **Aluminum box** renders in the viewer (visible as small thumbnail in bottom-left)

## Open issue 1: XCAF label names not extracted

**Symptom**: Assembly tree shows `solid_0000`, `solid_0001`, etc. instead of real part names.

**Analysis**: The XCAF reader runs successfully (no fallback to plain reader, `step_tags.extracted` log confirms tags were extracted). But `_get_label_name()` in `step_loader.py` returns `None` for all labels.

**Likely cause**: The `TDocStd_Application` + `binxcafdrivers.DefineFormat` + `NewDocument("BinXCAF")` initialization creates the XCAF document differently than the original `TCollection_ExtendedString("XDE")` path. The `STEPCAFControl_Reader.Transfer(handle)` may populate the label tree with a different structure or attribute set. Specifically:

- `TDataStd_Name.GetID()` may not be the right attribute ID for BinXCAF documents
- The label tree walk via `ShapeTool.GetFreeShapes()` / `ShapeTool.GetComponents()` may return labels without `TDataStd_Name` attributes attached
- pythonocc-core's own `read_step_file_with_names_colors` utility in `DataExchange.py` uses a different approach — it calls `STEPCAFControl_Reader` with `"pythonocc-doc-step-import"` as the document format string, not `"BinXCAF"`. Worth testing.

**Investigation path**:
1. Try `"pythonocc-doc-step-import"` or `"XmlXCAF"` as the format string instead of `"BinXCAF"`
2. Check pythonocc's own `read_step_file_with_names_colors` source code for the exact init pattern
3. Test `label.GetLabelName()` as an alternative to `TDataStd_Name.GetID()`
4. Print the full label attribute list to see what IS populated
5. Test on a STEP file known to have XCAF names (create one in FreeCAD with explicit part names)

**Files**: `src/raysim/geom/step_loader.py` lines 91-130 (`_load_step_xcaf`), lines 230-245 (`_get_label_name`)

## Open issue 2: OCCT viewer uses Mesa software renderer instead of GPU

**Symptom**: Viewer renders the model in a tiny rectangle in the bottom-left corner of the viewer widget. The rest is black. FitAll doesn't fix it.

**Analysis**: Console shows `GLdevice: llvmpipe (LLVM 20.1.8, 256 bits)` — Mesa software renderer. The previous install (with novtk pythonocc 7.9.0) used `GLdevice: AMD Radeon (TM) 860M` — the real GPU. After reinstalling with pythonocc 7.9.3, Mesa is used instead.

**Likely cause**: pythonocc-core 7.9.3 (or its OCCT 7.9.3 dependency) ships or depends on Mesa/llvmpipe OpenGL libraries that override the system AMD driver in the DLL search path. The `Library\bin` directory we add via `os.add_dll_directory()` may contain Mesa's `opengl32.dll` that shadows the system one.

**Investigation path**:
1. Check `%LOCALAPPDATA%\raysim-micromamba\envs\raysim-ui\Library\bin\` for `opengl32.dll` or `libGL*.dll` — if present, Mesa is bundled
2. Try setting `LIBGL_ALWAYS_INDIRECT=1` or removing the Mesa DLLs
3. Compare DLL contents between 7.9.0 novtk and 7.9.3 novtk installs
4. Check if pythonocc-core 7.9.3 pulls in `mesalib` as a conda dependency
5. Try `$env:MESA_GL_VERSION_OVERRIDE="4.6"` to see if it's a version-cap issue
6. Test with the `all` build variant (includes VTK which has its own GL driver selection)

**Impact**: The model IS rendering (visible in the bottom-left corner), just in a wrong viewport size. The software renderer is also much slower than GPU. This blocks practical UI testing on Windows.

**Files**: `src/raysim/ui/viewer.py` (viewer init), `src/raysim/ui/app.py` (launch sequence)

## Environment details

- **OS**: Windows 11, AMD Radeon 860M GPU
- **Python**: 3.12 (conda-forge via micromamba)
- **pythonocc-core**: 7.9.3 novtk (conda-forge win-64)
- **PySide6**: 6.11.0 (conda-forge)
- **OpenGL**: Mesa llvmpipe 4.5 (should be AMD 4.6)
- **micromamba root**: `%LOCALAPPDATA%\raysim-micromamba`

## What was fixed during this session

| Issue | Fix | Commit |
|-------|-----|--------|
| `load_backend("pyside6")` missing | Added to `viewer.py` | `04c9bfe` |
| OCCT DLLs not on PATH | Added `os.add_dll_directory` to `cli/main.py` | `260a7fd` |
| CMD line too long for micromamba | Launchers call Python directly | `260a7fd` |
| VBS quote escaping broken | Fixed PowerShell string generation | `4252f8a` |
| `pythonw.exe` for no-console launch | VBS uses `pythonw.exe` | `3249117` |
| `TDocStd_Document` C++ crash | `TDocStd_Application` + `binxcafdrivers` workaround | `5d3e7e9` |
| O(N²) overlap freezing UI | Deferred pipeline to run time | `91628f8` |
| novtk XCAF detection | Platform-based check (now replaced by workaround) | `d115008` |
| Long Windows paths (Qt headers) | `robocopy /MIR` in cleanup script | `4ec0435` |
| Long paths disabled | Pre-check + admin instructions in install script | `b7b94b0` |

## Next steps

1. ~~Fix XCAF label name extraction (issue 1 above)~~ — **Fixed in v0.3.1**: `GetLabelName()` + instance/prototype separation
2. ~~Fix Mesa/viewport rendering (issue 2 above)~~ — **Fixed**: renamed Mesa `opengl32.dll`, added deferred viewport resize, applied assembly placement transforms via accumulated `TopLoc_Location`
3. Once both fixed: test full flow (open STEP → assign materials → place detectors → load .dos → run → view results)
4. Push and verify CI
5. Implement the v0.4.0 overlap decoupling plan (`docs/1-plans/F_0.4.0_decouple-overlap-diagnostic.plan.md`)
