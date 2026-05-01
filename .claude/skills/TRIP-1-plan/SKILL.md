---
name: TRIP-1-plan
description: Plan a new feature following project standards
argument-hint: "describe the feature you want to build"
---

# Planning Mode — RaySim

## Prerequisites

Read ALL lines of @docs/ARCHI.md before creating any plan.

## Task

Plan: $ARGUMENTS

---

## Step 1: Discovery (Interactive)

Do NOT write the plan yet. First clarify the feature with the user.

Summarize your understanding in 2-3 sentences, then use `AskUserQuestion` with 2-4 concrete options covering scope, behavior, constraints, and priority.

Iterate until clear. When ready, propose an approach and confirm via `AskUserQuestion`: "Based on your answers, the approach would be: [brief]. Does this align?" Options: "Yes, proceed" / "Adjust".

---

## Step 2: Create Plan Document

### File Naming

Propose SemVer version, create: `docs/1-plans/F_[version]_[feature-name].plan.md`

### Template

```markdown
# [Feature Name] Implementation Plan

## Overview
[2-4 sentences: feature and purpose]

## Problem Statement (if applicable)
[Current limitations this addresses]

## Solution Architecture
[High-level design approach]

## Implementation Details

### 1. [Component/Module/File Name]
**File**: `path/to/file`
[Detailed description of changes]

**Current state** (if modifying existing):
[What currently exists]

**Modifications**:
- Specific change 1 (around line X)
- Specific change 2 (around line Y)

### 2. [Next Component]
[Same pattern]

## Technical Considerations
- **Pattern Usage**: Which existing patterns to follow (ARCHI.md §5).
- **Determinism Impact**: Does this affect `run.json` bit-identity? Ordered reductions? Canonical JSON? `Provenance` hashes? Schema_version bump? (ARCHI §14)
- **Numerical Precision**: Float32/64 boundary? eps-gap accounting? A.7 1e-5 hard gate? (ARCHI §15)
- **Material Physics Scope**: MVP uses `density_g_cm3` only; `z_eff`/composition in dose math = scope expansion needing justification.
- **Coincident-Face / Tied-Batch**: Scene/BVH/traversal changes must preserve tied-batch invariants (ARCHI §11). embreex 4.4 has no filter callback.
- **Backend Optionality**: `embreex`, `healpy`, `pythonocc-core` are optional. Guard with `pytest.importorskip` (tests) or document the extra.
- **Schema Versioning**: Breaking `proj.schema`/`env.schema` changes require `SCHEMA_VERSION` bump. Document v_old → v_new diff.
- **Edge Cases**: Empty stacks, missing solids, negative thicknesses, pure-zero species, t=0 LOS rays, max-hit safety cap.

## Files to Modify/Create
1. `path/to/file1` (modify) - Purpose
2. `path/to/file2` (new) - Purpose

## Type Definitions (if applicable)
[New/modified types]

## Performance & Cost Impact (if applicable)
[Expected implications]

## Backward Compatibility (if applicable)
[Migration strategy]

## To-dos

### Phase 1: [Name] (skip title if single phase)
- [ ] Task description
- [ ] Another task

### Phase 2: [Name] (if applicable)
- [ ] Task description

**Note**: Single phase is sufficient for simple plans. Testing is OUT OF SCOPE.
```

### Quality Standards

Every step must be actionable with file-level specificity. Must conform to ARCHI.md patterns. Highlight potential failure points.

---

## Step 3: Codex Second-Opinion Review

Before the user sees the plan, run the Codex plan review loop.

### Confirm

`AskUserQuestion`: "I'll run Codex as a second-opinion reviewer and iterate until clean. Proceed?"
Options: "Yes, run Codex review" (recommended) / "Skip Codex, go to user review" / "Cap iterations at N"

Skip for trivial plans (single-file, low-risk). Run for non-trivial (new module, schema/algorithm change).

### Loop

1. **Start**: `bash .claude/skills/codex-plan-review/scripts/start.sh --prompt-file .claude/skills/codex-plan-review/prompts/start.tpl <plan-path>`
2. **Parse trailing tag**: `APPROVED` → Step 4. `NEEDS_REWORK` → surface to user. `REQUEST_CHANGES` → continue.
3. **Address findings critically** — quote each P1/P2, push back on incorrect ones, fix legitimate ones by editing the plan in place.
4. **Write implementer notes** (1-3 sentences): which findings you fixed, which you pushed back on and why, any user decisions that override existing docs or environment limitations that can't be resolved in the plan.
5. **Resume** with notes:
   ```bash
   bash .claude/skills/codex-plan-review/scripts/resume.sh \
       --prompt-file .claude/skills/codex-plan-review/prompts/resume.tpl \
       --notes "Fixed X. Pushed back on Y because Z. User decided W." \
       <plan-path>
   ```
   → back to step 2.
6. **Cap at 5 rounds** (or user-specified). Surface remaining findings and let user decide.

Surface Codex reviews verbatim. Keep edits scoped to findings. Reset thread (`reset.sh <plan-path>`) only if context is genuinely confused.

---

## Step 4: User Review

Present summary: feature name, approach (1-2 sentences), files affected, complexity (simple/moderate/complex), Codex status.

`AskUserQuestion`: "Review the plan at `<path>`. How to proceed?"
Options: "Approved" / "Request changes" / "Needs rework"

- **Request changes**: update plan, re-present. Run another Codex pass if changes are substantive.
- **Needs rework**: discuss, rework, re-present.
- **Approved**: ask "Plan approved. Start implementation now?" Options: "Yes, implement now" (→ TRIP-2-implement) / "Not yet"

---

## No Code Implementation

Do NOT write code during planning. Describe WHAT, WHERE, and WHY — not HOW in code.

---

## Per-Component Planning Guidance

Pick sections matching the change.

### Ray-engine (`raysim.ray.tracer`, `raysim.ray.scene`)
- Stack-accumulator: entry on negative-dot / exit on positive-dot invariant preserved?
- Tie-batch: new batch formation? Sort order still `(geom_id, prim_id)` ascending?
- eps-gap correction still applied after every batch?
- Termination invariants (stack_leak, overlap_suspicious, max_hit)?
- A.7 1e-5 hard gate (concentric-shell, principal-axis): pass/fail prediction?
- Float32/float64 boundary location?

### Dose-math (`raysim.dose.spline`, `raysim.dose.aggregator`)
- Edge cases: t=0, t<t_min, t>t_max, pure-zero species, mixed-zero, monotonicity bumps.
- Per-species reconciliation: `sum(per-species) == total` for DDCs with non-trivial extras?
- mm-Al-equivalent: still `RHO_AL_REF_G_CM3 = 2.70`? Physics justification if changed.
- Field naming: never `sigma`/`±σ` — `angular_spread` and `shielding_pctile` only (ARCHI §12.3).

### Environment importers (`raysim.env.importers.<dialect>`)
- Output is canonical `DoseDepthCurve` — no dialect-specific schema escaping.
- Unit conversion at boundary with explicit constants.
- Per-species column mapping: canonical names, extras, unrecognized-column handling.
- Mission metadata captured without parsing/normalizing.
- Fixture under `tests/fixtures/` plus round-trip test.

### Scene/geometry (`raysim.geom`, Stage B)
- STEP feature support (AP203/AP214/AP242, assembly tree depth).
- Healing strategy (`BRepMesh_ModelHealer` vs hand-written fallback).
- Outward-pointing normal convention (ARCHI §11) including hollow solids.
- Per-shell watertightness — pass/fail/override path.
- Coincident-face classification: `contact_only`, `accepted_nested`, `interference_warning`, `interference_fail`.

### CLI (`raysim.cli.*`)
- Determinism: new output → `run.json` (canonical JSON) or sibling human file (free)?
- Provenance: new inputs affecting the answer must hash into `Provenance`.
- Exit codes: 0 success, 1 click error, 1 run-fatal.
- I/O: stdout for one-line confirmation, stderr for structlog.

### Schemas (`raysim.proj`, `raysim.env.schema`)
- `SCHEMA_VERSION` bump if breaking.
- Loader accepts N-1 for one release.
- Pydantic `extra="forbid"` on every input model.
- Field naming: `*_mm`, `*_g_cm3`, `*_krad`, `*_g_cm2`.
