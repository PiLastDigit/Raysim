# Code Review: Fix XCAF label name extraction + instance/prototype name columns

**Review Date**: 2026-05-01
**Version**: 0.3.1
**Files Reviewed**:
- `src/raysim/geom/step_loader.py`
- `src/raysim/ui/panels/tree_panel.py`
- `src/raysim/mat/rules.py`
- `src/raysim/ui/state.py`
**Plan**: no plan — unplanned bugfix + enhancement

---

## Executive Summary

Fixes broken XCAF label name extraction (root cause: pythonocc SWIG `FindAttribute` type mismatch silently caught) by switching to `GetLabelName()` and the `"pythonocc-doc-step-import"` document format. Separates XCAF instance names (e.g. "R41") from prototype names (e.g. "R_0402_1005Metric") into distinct `LeafSolid` fields, adds a "Part" column to the assembly tree, and extends naming-rule matching to cover both. APPROVED.

---

## Changes Overview

`step_loader.py`: `_get_label_name` now uses `TDF_Label.GetLabelName()` (pythonocc's own pattern) instead of the broken `FindAttribute` path. `_create_xcaf_document` tries `TDocStd_Document("pythonocc-doc-step-import")` first. `_walk_label` separates instance name (from component/reference label) vs prototype name (from referred shape label) into `LeafSolid.name` and `LeafSolid.part_name`. `_walk_compound` propagates both names to child solids.

`tree_panel.py`: 4-column layout (Name, Part, Solid ID, Material) with shifted column indices.

`rules.py`: `SolidRef` gains `part_name` field; `apply_rules` matches against all four targets.

---

## Findings

### Critical Issues

None.

### Major Issues

1. **`_walk_compound` dropped names for compound-contained leaves** — `step_loader.py:340-344`. Child solids inside a COMPOUND/COMPSOLID received `label_name=None, part_name=None`. Fixed by propagating the parent's resolved names. Addressed in Turn 2.

### Minor Issues

None.

### Suggestions

None.

---

## Checklist

- [x] 1. Functional Requirements — passed (compound propagation fixed in Turn 2)
- [x] 2. Code Quality — passed
- [x] 3. Architectural Compliance — passed
- [x] 4. Determinism & Reproducibility — not applicable (no deterministic output impact)
- [x] 5. Numerical Precision — not applicable
- [x] 6. Stack Accumulator Invariants — not applicable
- [x] 7. Material Physics Scope — not applicable
- [x] 8. Error Handling — passed
- [x] 9. Performance — passed
- [x] 10. Optional-Backend Hygiene — passed

---

## Verdict

**APPROVED**

Codex review converged in 2 rounds. Turn 1 flagged compound-contained leaf name propagation; addressed before Turn 2. All 179 uv tests + 25 conda tests (step_loader + rules) pass. ruff + mypy clean. Windows GUI tested — names display correctly.
