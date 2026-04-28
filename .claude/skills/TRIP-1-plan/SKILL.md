---
name: TRIP-1-plan
description: Plan a new feature following project standards
argument-hint: "describe the feature you want to build"
---

# Planning Mode

You are now in **planning mode** for **RaySim**.

## Prerequisites - Read First

Before creating any plan, you MUST read ALL THE LINES of:

1. @docs/ARCHI.md - Understand current system architecture

## Your Task

Plan the following feature: $ARGUMENTS

---

## Step 1: Discovery & Clarification (Interactive)

**Do NOT start writing a plan immediately.** First, engage in a discovery conversation to fully understand the user's intent.

### 1.1 Initial Understanding

After reading the feature request, summarize your understanding in 2-3 sentences, then **use the `AskUserQuestion` tool** to present clarifying questions with structured options.

Frame questions around:

- **Scope**: What's included vs excluded?
- **Behavior**: How should it work from the user's perspective?
- **Constraints**: Any technical limitations, deadlines, or dependencies?
- **Priority**: What's most important if trade-offs are needed?

For each question, provide 2-4 concrete options based on your analysis of the codebase and the feature request. Always let the user provide custom input via the built-in "Other" option.

### 1.2 Iterate Until Clear

After user answers, either:

- **Ask follow-up questions** using the `AskUserQuestion` tool if new ambiguities emerged
- **Propose an approach** and **use the `AskUserQuestion` tool** to confirm:
  - **Question**: "Based on your answers, I'm thinking the approach would be: [brief description]. Does this align with what you have in mind?"
  - **Options**: "Yes, proceed" (approach looks good), "Adjust" (I have modifications to suggest)

---

## Step 2: Plan Document Creation

Once understanding is confirmed, create the plan document.

### File Naming

Depending on the feature (major, minor, patch), propose a new version using SemVer (x.y.z) and create:
`docs/1-plans/F_[version]_[feature-name].plan.md`

### Required Sections

```markdown
# [Feature Name] Implementation Plan

## Overview

[2-4 sentences describing the feature and its purpose]

## Problem Statement (if applicable)

[Current limitations/issues this feature addresses]

## Solution Architecture

[High-level design approach]

## Implementation Details

### 1. [Component/Module/File Name]

**File**: `path/to/file`

[Detailed description of changes needed]

**Current state** (if modifying existing):
[Describe what currently exists]

**Modifications**:

- Specific change 1 (around line X)
- Specific change 2 (around line Y)

### 2. [Next Component/Module/File]

[Continue with same pattern]

## Technical Considerations

- **Pattern Usage**: Which existing patterns to follow (from ARCHI.md §5
  Core Architecture Principles).
- **Determinism Impact**: Does this change affect `run.json` bit-identity?
  If yes: ordered reductions preserved? canonical JSON used for any new
  output? new inputs added to `Provenance` hashes? schema_version bump
  needed? (See ARCHI §14 — this is a contract, not a goal.)
- **Numerical Precision**: If touching the ray engine or dose math, what's
  the float32 / float64 boundary? Does the eps-gap accounting still hold?
  Does the change risk the A.7 1e-5 hard gate? (See ARCHI §15.)
- **Material Physics Scope**: MVP uses `density_g_cm3` only; everything
  else (`z_eff`, composition) is metadata. If a plan reaches for those
  fields in the dose math, that's a scope expansion and needs explicit
  justification.
- **Coincident-Face / Tied-Batch**: Any change to scene loading, BVH
  building, or traversal must preserve the tied-batch invariants (ARCHI
  §11). embreex 4.4 has no filter callback — pre-built groups are mandatory.
- **Backend Optionality**: `embreex`, `healpy`, `pythonocc-core` are
  optional dependencies. Code that uses them must guard with
  `pytest.importorskip` (tests) or document the extra in the install path.
- **Schema Versioning**: Breaking changes to `proj.schema` or `env.schema`
  require a `SCHEMA_VERSION` bump. Document the v_old → v_new diff in the
  plan.
- **Edge Cases**: Empty stacks, missing solids, negative thicknesses,
  pure-zero species columns, t = 0 LOS rays, max-hit safety cap.

## Files to Modify/Create

[Comprehensive numbered list with purposes]

1. `path/to/file1` (modify) - Purpose description
2. `path/to/file2` (new) - Purpose description

## Type Definitions (if applicable)

[New types, interfaces, structs, or modifications to existing ones]

## Performance & Cost Impact (if applicable)

[Expected performance implications]

## Backward Compatibility (if applicable)

[Migration strategy if needed]

## To-dos

### Phase 1: [Phase Name] (if multiple phases are needed) or simply skip title if only one phase is needed

- [ ] Task description
- [ ] Another task

### Phase 2: [Phase Name] (if applicable)

- [ ] Task description
- [ ] Another task

**Note**: For simple plans, a single phase is sufficient. Split into multiple phases only for complex features requiring sequential implementation.

**Note**: Testing is OUT OF SCOPE for planning - will be handled separately.
```

## Quality Standards

- **Zero Ambiguity**: Every step must be clear and actionable
- **File-Level Specificity**: List exact files and functions to modify
- **Architecture Alignment**: Must conform to existing patterns in ARCHI.md
- **Risk Assessment**: Highlight potential failure points

---

## Step 3: Plan Review & Validation

After creating the plan document, present a summary to the user including:

- **Feature**: [name]
- **Approach**: [1-2 sentences]
- **Files affected**: [count] files ([list key ones])
- **Estimated complexity**: [simple/moderate/complex]

Then **use the `AskUserQuestion` tool** to collect feedback:

- **Question**: "Please review the plan at `docs/1-plans/F_x.y.z_feature-name.plan.md`. How would you like to proceed?"
- **Options**: "Approved" (ready for implementation), "Request changes" (I have modifications), "Needs rework" (significant issues to address)

Handle feedback:

- **If "Request changes"**: Update the plan and re-present using `AskUserQuestion` again
- **If "Needs rework"**: Discuss issues, rework the plan, and re-present
- **If "Other" (custom input)**: Handle accordingly
- **If "Approved"**: **Use the `AskUserQuestion` tool** to ask:
  - **Question**: "Plan approved. Would you like to start implementation now?"
  - **Options**: "Yes, implement now" (proceed with `TRIP-2-implement` using this plan), "Not yet" (I'll implement later)

---

## IMPORTANT: No Code Implementation

**DO NOT write code snippets or implement anything during planning.**

This is a high-level planning phase only. Your plan should describe:

- WHAT needs to be done (features, changes, structures)
- WHERE changes will happen (files, modules, functions)
- WHY certain approaches are chosen (trade-offs, rationale)

But NOT:

- Actual code implementations
- Detailed algorithm code

Keep it architectural and descriptive. Code comes in the `TRIP-2-implement` phase.

---

## Per-Component Planning Guidance

The major architectural surfaces in RaySim each carry their own set of
required-analysis items. Pick the section(s) that match the change.

### For new ray-engine work (`raysim.ray.tracer`, `raysim.ray.scene`)

Required analysis:

- Stack-accumulator semantics: does the change preserve the entry-on-
  negative-dot / exit-on-positive-dot invariant?
- Tie-batch handling: any new way a batch can form? Sort order still
  `(geom_id, prim_id)` ascending?
- eps-gap correction still applied after every batch?
- Termination invariants (stack_leak, overlap_suspicious, max_hit)?
- A.7 1e-5 hard gate impact (concentric-shell, principal-axis): pass/fail
  prediction and how to verify.
- Float32 / float64 boundary: where does the precision cliff sit?

### For new dose-math work (`raysim.dose.spline`, `raysim.dose.aggregator`)

Required analysis:

- Edge-case coverage: t = 0, t < t_min, t > t_max, pure-zero species,
  mixed-zero species, monotonicity bumps.
- Per-species reconciliation: does `sum(per-species)` still equal `total`
  for DDCs with non-trivial extras?
- mm-Al-equivalent reference density: still `RHO_AL_REF_G_CM3 = 2.70`?
  If changed, document the physics justification.
- Field naming: never `sigma`, never `±σ` — `angular_spread` and
  `shielding_pctile` only (ARCHI §12.3).

### For new environment importers (`raysim.env.importers.<dialect>`)

Required analysis:

- Output is the canonical `DoseDepthCurve` from `raysim.env.schema` — no
  dialect-specific schema escaping.
- Unit conversion at the boundary (rad → krad, energy → mm_Al-eq, etc.)
  with explicit constants.
- Per-species column mapping: which canonical names, which extras, how
  is "everything I don't recognize" handled?
- Mission metadata captured into the result without parsing/normalizing.
- Fixture file added under `tests/fixtures/` plus a round-trip test.

### For new scene/geometry work (`raysim.geom`, Stage B)

Required analysis (deferred to Phase B1):

- STEP feature support (AP203/AP214/AP242, assembly tree depth).
- Healing strategy (`BRepMesh_ModelHealer` vs the hand-written fallback).
- Outward-pointing normal convention (ARCHI §11) — including hollow
  solids' cavity sub-shells.
- Per-shell watertightness — pass list, fail list, override path.
- Coincident-face classification: `contact_only`, `accepted_nested`,
  `interference_warning`, `interference_fail`.

### For new CLI subcommands (`raysim.cli.*`)

Required analysis:

- Determinism: does the new output go into `run.json` (canonical JSON
  required) or a sibling human file (free)?
- Provenance: any new input that affects the answer must hash into
  `Provenance`.
- Exit codes: 0 success, 1 click error, 1 run-fatal. No new conventions.
- I/O streams: stdout for the one-line confirmation, stderr for structlog.

### For new schemas / project file format (`raysim.proj`, `raysim.env.schema`)

Required analysis:

- `SCHEMA_VERSION` bump if the change is breaking.
- Loader continues to accept `N-1` for one release (per `MVP_PLAN.md §10`
  policy).
- Pydantic `extra="forbid"` on every input model.
- Field naming consistent with existing conventions (`*_mm` for lengths,
  `*_g_cm3` for densities, `*_krad` for doses, `*_g_cm2` for mass-thickness).
