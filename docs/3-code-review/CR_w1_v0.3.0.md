# Code Review: Phase B3 — UI + Authoring

**Review Date**: 2026-04-30
**Version**: 0.3.0
**Files Reviewed**:
- `MVP_STEPS.md`
- `docs/ARCHI.md`
- `src/raysim/cli/main.py`
- `src/raysim/geom/step_loader.py`
- `src/raysim/mat/step_tags.py`
- `src/raysim/ui/__init__.py`
- `tests/unit/test_mat_step_tags.py`
- `tests/unit/test_step_loader.py`

**Plan**: `docs/1-plans/F_0.3.0_phase-b3-ui-authoring.plan.md`

---

## Executive Summary

The change implements Phase B3 UI authoring foundations: XCAF STEP loading, simplified STEP tag extraction, a PySide6 GUI entry point, UI state, panels, viewer, overlays, and run worker dispatch. The review loop resolved several correctness and determinism risks, including stale material scenes, missing `run.json` output, missing max-hit fatal handling, project reload gaps, and run-readiness bypasses. Final verdict: NEEDS REVISION.

---

## Changes Overview

The tracked diff migrates `raysim.geom.step_loader` to `STEPCAFControl_Reader`, adds XCAF metadata fields to geometry records, simplifies `raysim.mat.step_tags.extract_step_tags()` to consume `LeafSolid` fields, and adds the `raysim gui` CLI command. The working tree also includes new untracked UI modules under `src/raysim/ui/` for the application shell, viewer, panels, overlays, state controller, and run worker. Tests were updated for the new STEP tag signature and XCAF loader behavior, including a DFS-order regression test scaffold.

---

## Findings

### Critical Issues

- **Stale material assignments could produce incorrect dose results** — `src/raysim/ui/state.py:326`, `src/raysim/ui/state.py:413` — Initial implementation built/reused a scene independently of later material assignment edits, risking runs with stale densities. **Disposition: addressed.** Assignment changes now rebuild the scene and run context hashes current assignments.
- **Clearing assignments could produce a stale-scene run with empty assignment provenance** — `src/raysim/ui/state.py:349`, `src/raysim/ui/state.py:401` — Clearing assignments originally left the old scene available and menu-triggered runs could bypass the disabled button. **Disposition: addressed.** Clearing assignments rebuilds/clears scene state, and run context blocks unless material gating is ready.

### Major Issues

- **GUI did not write `run.json`** — `src/raysim/ui/panels/run_panel.py:81`, `src/raysim/ui/workers/run_worker.py:120` — Initial GUI runs had no output path and therefore never wrote the planned canonical `run.json`. **Disposition: addressed.**
- **GUI run dispatch missed the max-hit fatal gate** — `src/raysim/ui/workers/run_worker.py:107` — Initial worker emitted successful completion even when `DetectorResult.n_max_hit_rays` was nonzero. **Disposition: addressed.**
- **Detector placement snap modes are incomplete** — `src/raysim/ui/panels/detector_panel.py:69`, `src/raysim/ui/viewer.py:184`, `src/raysim/ui/viewer.py:190` — Snap controls and normal-offset plumbing were added, but `"free"` mode still returns `_face_centroid(shp)`, so free-position placement is not implemented as specified by the plan. **Disposition: open.**
- **XCAF DFS-order regression guard is not a checked-in golden test** — `tests/unit/test_step_loader.py:91`, `tests/unit/test_step_loader.py:128`, `docs/1-plans/F_0.3.0_phase-b3-ui-authoring.plan.md:102` — The test validates bbox values once a golden file exists, but still generates `tests/fixtures/step_leaf_golden.yaml` during test execution and skips when absent. The plan requires a checked-in fixture. **Disposition: open.**
- **Opening an existing project did not reload geometry** — `src/raysim/ui/state.py:172` — Initial `open_project()` loaded assignments/detectors/dose curve but not the referenced STEP geometry. **Disposition: addressed.**
- **Scene rebuild swallowed all build failures** — `src/raysim/ui/state.py:251`, `src/raysim/ui/state.py:273` — Initial broad exception handling hid real geometry/backend failures. **Disposition: addressed.** Only incomplete-assignment `KeyError` is caught; other failures propagate.
- **Fresh or partially assigned STEP could crash before user review** — `src/raysim/ui/state.py:251`, `src/raysim/ui/state.py:273` — Early scene rebuild attempted to build with incomplete assignments and surfaced missing material errors before the UI could gate runs. **Disposition: addressed.** Incomplete-assignment failures are treated as soft state and run context reports actionable readiness errors.

### Minor Issues

- **Documentation/changelog gate incomplete** — `docs/ARCHI.md:274`, `docs/ARCHI.md:291`, `docs/2-changelog/changelog_table.md:3` — `ARCHI.md` was updated to describe the B3.0 XCAF and `extract_step_tags(leaves)` behavior. The changelog still lacks a `0.3.0` entry. **Disposition: partially addressed; changelog remains open.**
- **Saving projects with external dose curves could fail** — `src/raysim/ui/state.py:215` — Initial save logic called `relative_to()` unconditionally for the dose curve path. **Disposition: addressed.**
- **STEP loader ARCHI entry initially described the old reader/API** — `docs/ARCHI.md:274`, `docs/ARCHI.md:291` — Earlier docs still described `STEPControl_Reader` and second-reader STEP tags. **Disposition: addressed.**

### Suggestions

None.

---

## Checklist

- [ ] 1. Functional Requirements — passed with caveats: detector free-position snap mode and checked-in DFS golden fixture remain open.
- [x] 2. Code Quality — passed.
- [ ] 3. Architectural Compliance — passed with caveats: changelog update remains open.
- [x] 4. Determinism & Reproducibility — passed.
- [x] 5. Numerical Precision — passed.
- [x] 6. Stack Accumulator Invariants — passed.
- [x] 7. Material Physics Scope — passed.
- [x] 8. Error Handling — passed.
- [x] 9. Performance — passed.
- [x] 10. Optional-Backend Hygiene — passed.

---

## Verdict

**NEEDS REVISION**

The review loop resolved the high-risk stale-scene/provenance, run-output, max-hit, project-load, and error-handling issues. Remaining blockers are plan conformance items: free-position snap mode is not implemented despite the UI exposing it, and the STEP DFS regression guard still depends on generating its golden fixture during the test instead of checking in the required fixture. The changelog also needs the `0.3.0` entry before promotion.

