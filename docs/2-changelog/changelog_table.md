# Changelog Table

| Version | Week | Commit Message |
| ------- | ---- | -------------- |
| `0.4.0` | 1    | Decouple overlap diagnostic from pipeline, add on-demand validation |
| `0.3.1` | 1    | Fix XCAF name extraction, add instance/prototype name columns to assembly tree |
| `0.3.0` | 1    | Add Phase B3 UI + authoring: XCAF migration, PySide6 app, panels, overlays, run dispatch |
| `0.2.0` | 1    | Add Phase B2 materials + project file: library, rules, STEP tags, review, gating, .raysim format |
| `0.1.0` | 1    | Add Phase B1 geometry pipeline: STEP loader, tessellation, healing, overlap, adapter |
| `0.0.2` | 1    | chore: initialize TRIP workflow |

---

# Changelog Summary

- **v0.4.0 (Decouple Overlap Diagnostic — Week 1, 02-05-2026)**:
  Removed the slow O(N²) volume-intersection classification from the
  mandatory pipeline. Fast `extract_contacts()` stays inline; full
  `diagnose_overlaps` is on-demand via "Validate Geometry" button or
  `raysim validate` CLI. Validation runs off the GUI thread.

- **v0.3.1 (XCAF Name Fix — Week 1, 01-05-2026)**:
  Fixed broken XCAF label name extraction (`GetLabelName()` replaces
  `FindAttribute`). Separated instance names ("R41") from prototype names
  ("R_0402_1005Metric") into `LeafSolid.name` and `LeafSolid.part_name`.
  Assembly tree gains "Part" column. Naming rules match both names.

- **v0.3.0 (Phase B3 UI + Authoring — Week 1, 30-04-2026)**:
  - **XCAF migration**: `step_loader` migrated to `STEPCAFControl_Reader`.
    `LeafSolid` gains `name`/`color_rgb`/`material_hint`. `extract_step_tags()`
    simplified to pure mapping from `LeafSolid` fields.
  - **New package**: `raysim.ui` — PySide6 desktop app with OCCT viewer, 6
    dockable panels (tree, material, detector, scenario, run, result), 3
    overlays (ray-view, Mollweide, 6-face projection), QThread run dispatch.
  - **New CLI**: `raysim gui` entry point.
  - **Tests**: 3 new test files, XCAF field + DFS regression tests.

- **v0.2.0 (Phase B2 Materials + Project File — Week 1, 30-04-2026)**:
  - **New package**: `raysim.mat` — seeded material library (14 entries),
    naming-rule auto-assignment engine, STEP tag ingestion (OCCT-optional),
    auto-assignment review API, run gating + density anomaly warnings.
  - **New module**: `raysim.proj.project` — `.raysim` project file format.
  - **New type**: `SolidRef` for rules/review APIs.
  - **Data files**: `default_library.yaml`, `default_rules.yaml`.
  - **Tests**: 6 new test files (47 tests).

- **v0.1.0 (Phase B1 Geometry Pipeline — Week 1, 30-04-2026)**:
  - **New package**: `raysim.geom` — STEP loader, tessellation, healing,
    watertightness, overlap diagnostic, pipeline orchestrator, adapter.
  - **Additive change**: `raysim.ray.scene` gains `PreBuiltTiedGroups`,
    `tied_groups` parameter, and `process_meshes` flag.
  - **Fixture generator**: `scripts/build_step_fixtures.py` (10 STEP fixtures).
  - **Tests**: 7 new OCCT-dependent test files (skipped without pythonocc-core).

- **v0.0.2 (TRIP Initialization — Week 1, 28-04-2026)**:
  - **Setup**: Initialized TRIP workflow. Project classified as a
    Scientific/Engineering CLI tool (Stage A) evolving toward a Desktop
    App (Stage B) with Library/SDK characteristics throughout.
  - **Documentation**: Generated `docs/ARCHI.md` covering 23 sections
    including the RaySim-specific surfaces (geometry layer, ray engine,
    coincident-face handling, dose math, HEALPix sampling, determinism,
    numerical precision, validation strategy).
  - **TRIP Skills**: Adapted `TRIP-1-plan` (technical considerations,
    per-component planning guidance), `TRIP-2-implement` (version file
    `pyproject.toml` + `__init__.py`, week anchor `2026-04-27`, tutorial
    step enabled — Intermediate / all focuses / Balanced style),
    `TRIP-3-review` (10-section checklist incl. determinism, numerical
    precision, stack-accumulator invariants), `TRIP-4-test` (uv-based
    commands, RaySim-specific testing priorities).
  - **Files Added**: `docs/ARCHI.md`, `docs/ARCHI-rules.md`,
    `docs/2-changelog/changelog_table.md`, `docs/4-unit-tests/TESTING.md`,
    plus `docs/{1-plans,3-code-review,4-unit-tests,5-tuto,6-memo}/`
    folders.
