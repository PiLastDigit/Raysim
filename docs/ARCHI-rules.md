# Architecture Documentation Rules

[ARCHI.md](ARCHI.md) documents the RaySim architecture. After each task
(new feature, refactor, bug fix), determine whether ARCHI.md needs updating
and apply the rules below.

## When to Update

Update after any change that alters one of these:

- **Project structure** — new directories, moved files, new submodules.
- **Technology Stack** — added/removed/upgraded dependency.
- **Module boundaries or contracts** — what a module exposes or consumes.
- **Geometry layer** (`raysim.ray.scene`) — STL convention, BVH building,
  tied-group detection.
- **Ray engine** (`raysim.ray.tracer`) — traversal algorithm, stack
  accumulator semantics, eps-gap handling, max-hit / leak / overlap
  invariants.
- **Coincident-face handling** — anything in §11 that changes when
  embreex evolves or B1.5 lands.
- **Dose math** — DDC schema, spline edge cases, mm-Al-equivalent
  conversion, per-species reconciliation rules.
- **HEALPix sampling** — healpy / vendored fallback dispatch.
- **Determinism contract** — canonical JSON, ordered reductions,
  provenance hashing, schema_version.
- **Numerical precision** — float32/64 boundary, the A.7 hard gate.
- **Validation strategy** — analytic fixtures, identity tests, cross-tool
  comparison plans.
- **CLI surface** — new subcommand, new flag, new exit-code convention.
- **Build / deployment** — packaging tool decision, installer, CI matrix.

## How to Update by Change Type

### Major Feature / Refactor

Review the relevant ARCHI sections and update them concretely. Likely
candidates:

- §4 Project Structure (if files/folders moved)
- §5 Core Architecture Principles (only if a principle is being added,
  removed, or renegotiated — rare)
- §9 Geometry Layer / §10 Ray Engine / §11 Tied-Batch / §12 Dose Math /
  §13 HEALPix — the per-domain sections
- §14 Determinism (if any new input affects `run.json`)
- §15 Numerical Precision (if the float boundary moved)
- §17 Data Flow Diagrams (regenerate the affected diagram)

If the refactor introduced a new architectural surface not covered by
any existing section, **add a new section** rather than stretching an
existing one.

### Minor Feature / Enhancement

Update only the sections directly affected. Most minor features touch
one or two sections at most (e.g., a new importer touches §12.1; a new
CLI flag touches §8 + §14 if it affects determinism).

### Bug Fix

Usually no update needed. Exceptions:

- The bug revealed an architectural flaw that needs documenting (e.g.,
  the assignments-hash gap surfaced in code review → §14 explicitly lists
  `assignments_hash` after the v1 → v2 schema bump).
- The fix introduces a new invariant worth documenting (e.g., a new
  termination condition in the traversal loop).

### Dependency Changes

Update §3 Technology Stack with the new pin. If the dependency change
affects an architectural decision (e.g., embreex 5.x exposing filter
callbacks would unblock the §A.4 fallback path), update the relevant
domain section too.

### Schema Changes

Schema bumps to `proj.schema` or `env.schema` always require:

- §14 Determinism — note the v_old → v_new diff and what new field is
  hashed (if any).
- The relevant per-module section (§12.1 for env, §6 of the schema
  module's own area).

## Guidelines

- **Be precise and factual.** Document the actual codebase, not an
  idealized version.
- **Be concise.** Enough detail to understand and reproduce architectural
  decisions, not implementation specifics.
- **Reference actual file paths.** `raysim.ray.tracer.trace_rays`, not
  "the traversal function."
- **Update Mermaid diagrams** when data flow changes.
- **Cross-link to MVP_PLAN.md / MVP_STEPS.md** for scope justification —
  ARCHI.md describes *what is*, MVP docs describe *what should be*.
- **Token budget**: ARCHI.md is read in full at the start of every plan
  and implementation. Keep it under ~20,000 tokens. Use `bash
  .claude/skills/TRIP-compact/count-tokens.sh docs/ARCHI.md` to check.
- **Don't churn the structure** unless necessary. Section numbers are
  cited from review files and changelog entries; renumbering breaks
  external references.

## What ARCHI.md is Not

- **Not a tutorial.** Tutorials live in `docs/5-tuto/`.
- **Not a runbook.** Operational/install docs live in `docs/install/`.
- **Not a planning doc.** Plans live in `docs/1-plans/`.
- **Not a code review record.** Reviews live in `docs/3-code-review/`.

ARCHI.md is the answer to "how is RaySim built and why does it look the
way it does?" — nothing more, nothing less.
