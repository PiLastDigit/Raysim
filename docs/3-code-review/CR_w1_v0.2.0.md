# Code Review: Phase B2 — Materials + Project File

**Review Date**: 2026-04-30
**Version**: 0.2.0
**Files Reviewed**:
- `pyproject.toml`
- `src/raysim/__init__.py`
- `src/raysim/mat/__init__.py`
- `src/raysim/mat/library.py`
- `src/raysim/mat/rules.py`
- `src/raysim/mat/step_tags.py`
- `src/raysim/mat/review.py`
- `src/raysim/mat/gating.py`
- `src/raysim/mat/default_library.yaml`
- `src/raysim/mat/default_rules.yaml`
- `src/raysim/proj/project.py`
- `tests/unit/test_mat_library.py`
- `tests/unit/test_mat_rules.py`
- `tests/unit/test_mat_step_tags.py`
- `tests/unit/test_mat_review.py`
- `tests/unit/test_mat_gating.py`
- `tests/unit/test_proj_project.py`

**Plan**: `docs/1-plans/F_0.2.0_phase-b2-materials-project-file.plan.md`

---

## Executive Summary

Phase B2 adds the material governance layer, default material/rule libraries, assignment review/gating APIs, STEP material-tag matching, and `.raysim` project file support. All major behavioral findings from review were addressed with regression tests.

---

## Changes Overview

The change is additive to Stage B and does not touch ray tracing, dose math, stack accumulation, or the deterministic `run.json` schema. New modules: `raysim.mat` (library, rules, step_tags, review, gating) and `raysim.proj.project`.

---

## Findings

### Critical Issues

None.

### Major Issues

- **Blank STEP material tags could auto-assign to the first library material** — `src/raysim/mat/step_tags.py:199`, `tests/unit/test_mat_step_tags.py:50` — Addressed. Empty/whitespace-only tags are now treated as unmatched, with regression coverage.

- **Invalid manual assignments could be silently overridden by auto sources** — `src/raysim/mat/review.py:72`, `tests/unit/test_mat_review.py:111` — Addressed. Manual assignments now remain authoritative; unknown manual `group_id`s become unresolved, with regression coverage.

### Minor Issues

- **Unresolved manual assignments were omitted from the review summary** — `src/raysim/mat/review.py:170` — Addressed. The problem filter now includes any status with `material_group_id is None`.

### Suggestions

None.

---

## Checklist

- [x] 1. Functional Requirements — passed
- [x] 2. Code Quality — passed
- [x] 3. Architectural Compliance — passed
- [x] 4. Determinism & Reproducibility — passed
- [x] 5. Numerical Precision — not applicable
- [x] 6. Stack Accumulator Invariants — not applicable
- [x] 7. Material Physics Scope — passed
- [x] 8. Error Handling — passed
- [x] 9. Performance — passed
- [x] 10. Optional-Backend Hygiene — passed

---

## Verdict

**APPROVED with observations**

All major behavioral findings were addressed. Verification clean: ruff clean, mypy clean, pytest 178 passed, 0 failed, 9 skipped. Codex review loop: 3 rounds.
