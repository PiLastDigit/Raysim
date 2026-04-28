---
name: TRIP-3-review
description: Review code following project standards
disable-model-invocation: true
argument-hint: "version or feature to review"
---

# Review Mode

You are now in **code review mode** for **RaySim**.

Review: $ARGUMENTS

## Prerequisites - Read First

Before reviewing, you MUST read:

1. @docs/ARCHI.md - Verify architectural compliance
2. Related plan file in `docs/1-plans/` - Confirm implementation matches design
3. Related changelog entry in `docs/2-changelog/`

---

## Systematic Review Checklist

### 1. Functional Requirements

- [ ] Implementation logic matches requirements correctly
- [ ] Interface/API matches documented specifications
- [ ] Error scenarios handled with proper feedback
- [ ] Edge cases and boundary conditions validated

### 2. Code Quality

- [ ] Proper typing (no unjustified dynamic types)
- [ ] DRY principle - no code duplication
- [ ] KISS principle - not unnecessarily complex
- [ ] Consistent, descriptive naming conventions
- [ ] Complex logic has explanatory comments
- [ ] Files/modules not excessively large
- [ ] Imports/includes organized, unused ones removed

### 3. Architectural Compliance

- [ ] Code follows established patterns from ARCHI.md
- [ ] Module boundaries respected (no `geom` ↔ `dose` cross-imports;
      importers under `env.importers.<dialect>`; UI/report stay Stage B)
- [ ] Pydantic models use `extra="forbid"`; types are explicit (no
      unjustified `Any`)
- [ ] Public API surface (everything exported in a package's `__init__`)
      stays curated; new symbols added to `__all__` deliberately

### 4. Determinism & Reproducibility (ARCHI §14)

- [ ] All output to `run.json` goes through `raysim.proj.canonical_json`
      (sorted keys, `%.17g` floats); no direct `json.dumps`
- [ ] Reductions are ordered (HEALPix pixels in index order; detectors in
      input order; tie-batches sorted by `(geom_id, prim_id)`)
- [ ] Any new input that affects the answer is hashed into `Provenance`
      (geometry / materials / assignments / detectors / dose curve /
      build SHA / library versions / Nside / epsilon / seed)
- [ ] No timestamps, hostnames, or wall-clock fields in the deterministic
      stream (those go in `--human-metadata-out`)
- [ ] If the schema changed in a breaking way, `SCHEMA_VERSION` is bumped

### 5. Numerical Precision (ARCHI §15)

- [ ] Float64 chord-length accumulator preserved on the Python side; no
      accidental float32 collapse outside Embree
- [ ] eps-gap correction still applied after every batch in
      `raysim.ray.tracer`
- [ ] A.7 hard gate (concentric-shell ≤ 1e-5) still passes
- [ ] HEALPix `4π × mean = sum × dΩ` identity still holds
- [ ] No silent extrapolation past `[t_min, t_max]` — clamp + counted warning

### 6. Stack Accumulator Invariants (ARCHI §10–11)

- [ ] Entry classified by `dot(direction, normal) < 0`, exit by `> 0`
- [ ] Tangent grazes (dot == 0) produce no surface event
- [ ] Tied batches still sorted lexicographically by `(geom_id, prim_id)`
- [ ] Termination invariants preserved: stack_leak / overlap_suspicious /
      max_hit_exceeded all surfaced as counts in `DetectorResult`
- [ ] If a detector is inside a solid, the stack is seeded via
      `enclosing_solids` (no silent uncounted chord through enclosing
      material)

### 7. Material Physics Scope (ARCHI §15)

- [ ] Dose math uses `density_g_cm3` only — `z_eff`, composition, etc.
      stay metadata
- [ ] mm-Al-equivalent uses `RHO_AL_REF_G_CM3 = 2.70` (Al-6061 nominal)
- [ ] Per-species output covers canonical species *and* DDC `extra_species`;
      `sum(per-species) ≈ dose_total` reconciles to OMERE print precision

### 8. Error Handling

- [ ] Errors caught and handled — Pydantic `ValidationError` for schema,
      `click.ClickException` for run-fatal, structlog warnings for soft
      diagnostics
- [ ] Error messages are clear and actionable; include filenames, line
      numbers, or pixel/ray ids when relevant
- [ ] No silent fallbacks past contract-violating inputs (e.g., negative
      thicknesses still warn; floor doesn't hide bad data)

### 9. Performance

- [ ] No obvious regression vs the dev-benchmark target (Nside=64 ≤ 10 s)
- [ ] No unnecessary float64 ↔ float32 round-trips in the inner loop
- [ ] Batched Embree calls preserved; no per-ray `run()` calls
- [ ] Numpy vectorization where it matters (∑ρL accumulation, spline eval,
      HEALPix integration)

### 10. Optional-Backend Hygiene

- [ ] Code that uses `embreex`, `healpy`, `pythonocc-core` guards with
      `pytest.importorskip` in tests; runtime code uses platform markers
      or graceful fallback (per the healpy / vendored pix2vec dispatch)
- [ ] No direct `import healpy` or `import OCC` outside the modules that
      legitimately need them

---

## Issue Severity Classification

**Critical (Block Deployment)**:

- Security vulnerabilities
- Data corruption risks
- Breaking API/interface changes
- Authentication bypasses

**Major (Require Immediate Fix)**:

- Incorrect business logic
- Significant performance degradation
- Missing error handling
- Compilation/build errors

**Minor (Should Fix)**:

- Code style inconsistencies
- Missing documentation
- Code duplication
- Missing edge case handling

**Suggestions (Nice to Have)**:

- Performance optimizations
- Readability improvements
- Additional test coverage

---

## Review Completion Criteria

Minimum for approval:

- [ ] All functional requirements implemented
- [ ] No critical or major issues remaining
- [ ] Build/compilation successful
- [ ] All existing tests pass
- [ ] Documentation updated per project standards

---

## Post-Review: Create Review File

After completing the review, create a summary file in `docs/3-code-review/`.

**File naming**: `CR_wa_vx.y.z.md` (a=project week, x.y.z=version)

**Template**:

```markdown
# Code Review: [Feature/Change Name]

**Review Date**: [Date]
**Version**: x.y.z
**Files Reviewed**: [List of files]

---

## Executive Summary

[Brief assessment - APPROVED / APPROVED with observations / NEEDS REVISION]

---

## Changes Overview

[What was changed and why]

---

## Findings

### Critical Issues

[List or "None"]

### Major Issues

[List or "None"]

### Minor Issues

[List or "None"]

### Suggestions

[List or "None"]

---

## Checklist

- [ ] Functional requirements verified
- [ ] Code quality (DRY, KISS) verified
- [ ] Architectural compliance verified
- [ ] Error handling reviewed
- [ ] Performance impact assessed

---

## Verdict

**[APPROVED / NEEDS REVISION]**

[Final notes]
```

**Important:** the checklist in the review file must be checked after the review is properly completed.
You should always check all the points, but if for any reason you didn't check it, add a note explaining why.
