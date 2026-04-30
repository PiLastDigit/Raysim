# Changelog Table

| Version | Week | Commit Message |
| ------- | ---- | -------------- |
| `0.2.0` | 1    | Add Phase B2 materials + project file: library, rules, STEP tags, review, gating, .raysim format |
| `0.1.0` | 1    | Add Phase B1 geometry pipeline: STEP loader, tessellation, healing, overlap, adapter |
| `0.0.2` | 1    | chore: initialize TRIP workflow |

---

# Changelog Summary

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
