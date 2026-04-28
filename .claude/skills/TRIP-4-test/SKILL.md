---
name: TRIP-4-test
description: Write/run tests following project standards
disable-model-invocation: true
argument-hint: "component or feature to test"
---

# Testing Mode

You are now in **testing mode** for **RaySim**.

## Prerequisites - Read First

Before testing, you MUST read:

1. @docs/ARCHI.md - Understand system architecture
2. @docs/4-unit-tests/TESTING.md - Testing guidelines

## Your Task

Test: $ARGUMENTS

---

## Testing Guidelines

### Scope

- Only run tests for relevant files that changed (not the whole project)
- Focus on the new feature/fix/refactor

### Commands

```bash
# Run all tests (default loop, no slow markers)
uv run pytest

# Verbose, show prints (e.g., for the dev-benchmark timing line)
uv run pytest -v -s

# Run a specific file
uv run pytest tests/unit/test_tracer.py

# Run a specific test
uv run pytest tests/integration/test_phase_a_acceptance.py::test_a7_1_concentric_shell_float32_hard_gate

# Run only the Phase A acceptance suite
uv run pytest tests/integration/test_phase_a_acceptance.py

# Skip slow / benchmark tests
uv run pytest -m "not benchmark and not slow"

# Coverage (no coverage tool wired by default; add pytest-cov if needed)
uv run pytest --cov=raysim --cov-report=term-missing
```

### Test Structure

Tests live under `tests/`, mirroring `src/raysim/` one-to-one:

- `tests/unit/test_<module>.py` — one file per source module. Imports the
  module directly. Uses fixtures only when state is non-trivial.
- `tests/integration/` — end-to-end flows that cross module boundaries.
  The Phase A acceptance suite (`test_phase_a_acceptance.py`) is here; it
  codifies the five MVP_PLAN §6 gates.
- `tests/fixtures/` — input fixtures (currently `dose700km.dos`).

Markers (registered in `pyproject.toml`):

- `slow` — long-running tests excluded by default.
- `benchmark` — `pytest-benchmark` perf regressions.
- `needs_embree`, `needs_healpy`, `needs_occt` — backend-dependent skips.

Tests that need an optional backend use `pytest.importorskip("embreex")`
at the top of the file so CI legs without the extra still pass.

### Testing Priorities

**Unit Tests** (one per source module):

- Schema validators (`raysim.proj.schema`, `raysim.env.schema`):
  round-trip JSON, frozen-tuple semantics, `extra="forbid"` enforcement.
- Canonical JSON serializer: float-format determinism, sorted keys,
  non-finite handling (`NaN` / `Infinity` → quoted strings).
- Importers (`raysim.env.importers.<dialect>`): real fixture +
  ragged-input failure case + edge-case columns.
- Spline (`raysim.dose.spline`): power-law reproduction, edge cases
  (t=0, pure-zero species, mixed-zero floor, extras reconciliation).
- Scene loader (`raysim.ray.scene`): tied-group detection on the
  concentric-shell fixture, single-solid no-tie case, unknown-material
  failure.
- Tracer (`raysim.ray.tracer`): aluminum-box principal axis (1e-5),
  off-axis diagonal, concentric-shell tied batch, max-hit cap, miss path,
  tangent grazing.
- Aggregator: uniform-shield reproduction, per-species reconciliation
  with total, pixel-map toggle, box-detector NotImplementedError.
- CLI loaders: CSV vs YAML materials, dict vs list detector forms,
  empty-assignments path.

**Integration Tests** (`test_phase_a_acceptance.py` is the canonical set):

- A.7-1 — analytic ∑ρL ≤ 1e-5 on concentric shell (the float32 hard gate).
- A.7-2 — uniform-shield DDC reproduction on a solid sphere (≤0.5%).
- A.7-3 — `4π × mean = ∑ × dΩ` HEALPix identity (regression guard for
  the enclosing-solid seed path).
- A.7-4 — dev benchmark Nside=64 ≤ 10 s.
- A.7-5 — determinism: subprocess CLI twice → byte-identical run.json.
- `test_assignments_change_result_and_provenance` — provenance contract
  for `--assignments`.

**What to Test**:

- **Happy path** — at least one test that exercises the full module on
  realistic inputs (the OMERE fixture, the canonical analytic STLs).
- **Edge cases** — empty stack, missing canonical species, t=0 LOS rays,
  pure-zero columns, max-hit cap, deeply nested solids.
- **Determinism** — when adding a new output field, add a determinism
  test that runs the path twice and diffs bytes.
- **Reconciliation** — when adding a new species path, assert
  `sum(per-species) ≈ dose_total` to OMERE's print precision (~5e-3).
- **Backend optionality** — tests for embreex/healpy/occt code use
  `pytest.importorskip` so they skip cleanly in environments without
  the extra.

### Special test-writing notes for RaySim

- Use **real OMERE fixtures** for spline tests, not synthetic ones, so
  production paths are exercised end-to-end.
- For **float comparisons**, use `pytest.approx` with `rel=` by default;
  use `abs=` only when comparing to zero or near-zero.
- **Determinism tests run the CLI as a subprocess** — `subprocess.run`
  via `sys.executable -m raysim.cli.main` if `raysim` isn't on PATH —
  not `CliRunner`, so the entry point users hit is what's tested.
- **A.7 hard gate has no relaxation knob.** If your change makes the
  concentric-shell test fail at 1e-5, either fix the change or follow
  the documented escape hatch (parametric-distance reprojection in
  float64) and update `MVP_STEPS.md §A.7` with the new bound.

---

## Post-Testing Summary

After completing tests, create a summary file:

**File**: `docs/4-unit-tests/wa_vx.y.z_test.md`
(a = project week, x.y.z = version)

**Content**:

```markdown
# Test Summary - Week a, V. x.y.z

## What Was Tested

[List of tested components/functions]

## Test Results

- Total tests: X
- Passed: X
- Failed: X
- Coverage: X%

## Key Findings

[Any issues discovered, edge cases found, etc.]

## Notes

[Additional context or recommendations]
```
