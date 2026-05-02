# Code Review: Decouple Overlap Diagnostic from Pipeline

**Review Date**: 2026-05-02
**Version**: 0.4.0
**Files Reviewed**:
- `docs/1-plans/F_0.4.0_decouple-overlap-diagnostic.plan.md`
- `pyproject.toml`
- `src/raysim/__init__.py`
- `src/raysim/cli/main.py`
- `src/raysim/geom/__init__.py`
- `src/raysim/geom/adapter.py`
- `src/raysim/geom/overlap.py`
- `src/raysim/geom/pipeline.py`
- `src/raysim/ui/panels/run_panel.py`
- `src/raysim/ui/state.py`
- `src/raysim/ui/workers/run_worker.py`
- `src/raysim/ui/workers/validate_worker.py`
- `tests/unit/test_overlap.py`
- `uv.lock`
**Plan**: `docs/1-plans/F_0.4.0_decouple-overlap-diagnostic.plan.md`

---

## Executive Summary

This change decouples the slow full overlap/interference diagnostic from the mandatory STEP-to-Embree run path, keeping fast contact extraction inline while adding explicit CLI/UI validation paths and human-metadata traceability. Review iterations found issues in validate exit semantics, UI threading, validation metadata, and stale async validation state; all blocking issues were addressed or accepted with rationale. APPROVED

---

## Changes Overview

The geometry pipeline now builds `ContactReport` via `extract_contacts()` and leaves `ValidatedAssembly.overlaps` optional for on-demand full diagnostics. `raysim validate` runs the full overlap diagnostic from the CLI, while the UI adds a `Validate Geometry` action backed by `ValidateWorker` so the O(N²)/OCCT path does not block the main thread. UI run human metadata now records overlap validation status and summary counts without changing deterministic `run.json`.

---

## Findings

### Critical Issues

None.

### Major Issues

- **Validate CLI exited clean after undetermined boolean failures** — `src/raysim/cli/main.py:92`. Addressed: command now counts `report.boolean_failures` and exits `1`.
- **UI validation ran the slow full diagnostic on the GUI thread** — `src/raysim/ui/panels/run_panel.py:98`. Addressed: moved to `ValidateWorker` QThread.
- **Async validation result could be applied to the wrong geometry** — `src/raysim/ui/state.py:154`. Addressed: monotonic `geometry_revision` counter guards stale completions.

### Minor Issues

- **CLI `--accept-warnings` does not override boolean failures** — accepted with rationale: boolean failures are undetermined results, not warnings.
- **Validation status was not persisted into UI run human metadata** — addressed: `RunContext.overlap_validated` + `overlap_summary`.
- **Human metadata omitted planned overlap summary counts** — addressed: `_overlap_summary()` computes counts from stored report.

### Suggestions

None.

---

## Checklist

- [x] 1. Functional Requirements — passed
- [x] 2. Code Quality — passed
- [x] 3. Architectural Compliance — passed
- [x] 4. Determinism & Reproducibility — passed
- [x] 5. Numerical Precision — passed
- [x] 6. Stack Accumulator Invariants — passed
- [x] 7. Material Physics Scope — passed
- [x] 8. Error Handling — passed
- [x] 9. Performance — passed
- [x] 10. Optional-Backend Hygiene — passed

---

## Verdict

**APPROVED**

All review findings from the 4-round iteration loop were addressed or explicitly accepted with rationale. Phase 2 spatial-hash optimization is deferred to a separate PR.
