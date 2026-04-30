---
name: TRIP-2-implement
description: Implement a feature following TRIP plan
argument-hint: "plan file or feature to implement"
---

# Implementation Mode

You are now in **implementation mode** for **RaySim**.

## Prerequisites - Read First

Before implementing, you MUST read ALL THE LINES of:

1. @docs/ARCHI.md - Understand current system architecture

## Your Task

Implement: $ARGUMENTS

---

## Step 0: Branch Evaluation (Pre-Implementation)

After reading ARCHI.md, evaluate if this implementation warrants a dedicated branch.

### When to Suggest a Branch

Consider a dedicated branch if the task involves:

- Multiple files across different modules
- Changes that could break existing functionality
- Features that might need review before merging
- Work that spans multiple sessions
- Experimental or risky changes

### Ask the User

**Use the `AskUserQuestion` tool** to ask:

- **Question**: "This implementation involves [brief scope assessment]. Would you like me to create a dedicated branch?"
- **Options**:
  1. **"Yes, create branch"** — Suggested name: `feat/[short-description]` or `fix/[short-description]`
  2. **"No, stay on current branch"** — Continue on the current branch

### If YES

```bash
git checkout -b [branch-name]
```

Confirm branch creation before proceeding.

### If NO

Continue on the current branch.

---

## Implementation Rules

- Apply **DRY** and **KISS** principles
- Add explanatory comments but avoid over-commenting obvious code
- Strike the right balance between readability and maintainability
- Follow existing patterns from the codebase

---

## Implementation Phase

Proceed with the implementation following the plan or the task description.

---

## Post-Implementation Checklist

After completing the implementation:

- Cross the corresponding checkboxes in the plan todo list (if any)
- Run the Codex code review loop (next section)
- Then **use the `AskUserQuestion` tool** to ask:
  - **Question**: "Is the implementation complete?"
  - **Options**: "Yes, everything is complete" (proceed to post-implementation steps), "No, there are remaining items" (continue working)

---

## Codex Second-Opinion Code Review (Iterative)

Before asking the user "is the implementation complete?", run the **`codex-code-review`** skill on the change set and iterate until Codex returns `APPROVED` or the iteration cap is reached. Codex checks plan-conformance, correctness, ARCHI compliance, determinism, numerical precision, the stack-accumulator invariants, the material-physics scope, error handling, performance, and optional-backend hygiene against the systematic checklist in `.claude/skills/codex-code-review/prompts/start.tpl` (adapted from `.codex/skills/TRIP-3-review/SKILL.md`).

Letting Codex catch mechanical issues *before* the user is asked to sign off keeps the user-facing review focused on intent — not plan-conformance niggles, not Pydantic-`extra="forbid"` misses, not forgotten ordered reductions.

### Pre-step — run tests yourself, surface the result to Codex

Codex cannot execute `pytest` (its sandbox reads files but doesn't run arbitrary code under your test environment). Its approval gate explicitly requires tests green, so you must run them and pipe the verdict into Codex's `EXTRA_PROMPT` so the gate is grounded.

```bash
# Before invoking the codex-code-review skill, run:
uv run ruff check .  2>&1 | tee /tmp/_trip2-lint.txt
uv run mypy           2>&1 | tee /tmp/_trip2-mypy.txt
uv run pytest -q      2>&1 | tee /tmp/_trip2-pytest.txt
```

If any of the three fails, **fix the failures before starting the review loop** — Codex shouldn't waste a round telling you tests are red. After they're green, summarize the result for Codex's `EXTRA_PROMPT`:

```
ruff: clean | mypy: clean | pytest: 247 passed, 0 failed, 3 skipped
```

That summary string is what you pass as the trailing positional arg to `start.sh` / `resume.sh` (it lands in `{{EXTRA_PROMPT}}` in the prompt template). Codex now has observed test status to gate approval against, instead of guessing.

If the user explicitly skips Codex review, you can also skip this pre-step — but it's worth running anyway as a sanity check before the user-facing "Is the implementation complete?" question.

### Confirm with the user

**Use the `AskUserQuestion` tool** before kicking off the loop:

- **Question**: "Implementation looks done. I'll run the Codex CLI as a second-opinion code reviewer against the plan and iterate until it's clean. Proceed?"
- **Options**:
  - **"Yes, run Codex review"** (Recommended) — start the loop.
  - **"Skip Codex, go straight to user sign-off"** — jump to the "Is the implementation complete?" question.
  - **"Cap iterations at N"** — let the user pick a tighter bound than the default of 5.

For trivial changes (single-file patch, ≤ 50 LOC, no new modules) the user may prefer to skip. For non-trivial changes (any new module, schema change, algorithm change, ray-engine touch, dose-math touch) the loop is worth it.

### The iteration loop

1. **Turn 1**: start a fresh Codex thread keyed on the plan that drove this implementation (or, for unplanned work, a short free-form label — see the "no-plan target" note below):
   ```
   export STATE_DIR=".claude/skills/codex-code-review/state"
   TEST_SUMMARY="ruff: clean | mypy: clean | pytest: 247 passed, 0 failed, 3 skipped"
   bash .claude/skills/codex-plan-review/scripts/start.sh \
       --prompt-file .claude/skills/codex-code-review/prompts/start.tpl \
       docs/1-plans/F_x.y.z_feature-name.plan.md \
       "$TEST_SUMMARY"
   ```
   The shared scripts live under `codex-plan-review/scripts/`; the `STATE_DIR` export keeps code-review state separate from plan-review state for the same plan path. The trailing positional arg becomes Codex's `{{EXTRA_PROMPT}}` substitution — pass the pre-step's test summary so Codex's approval gate is grounded. The script writes the review to `.claude/skills/codex-code-review/state/<key>.review.txt` and prints it to stdout. Codex resolves the change set itself via `git diff HEAD` (read-only sandbox allows this).

2. **Parse the trailing tag**:
   - `APPROVED` → exit the loop, propose end-of-loop steps (below), then move to the user-facing "complete?" question.
   - `REQUEST_CHANGES` → continue to step 3.
   - `NEEDS_REWORK` → stop the loop and surface to the user — there are structural issues that warrant a conversation, not mechanical fixes.

3. **Address findings critically**. The review uses Critical / Major / Minor / Suggestion severity tags. For each finding:
   - Quote it back to the user with the cited `file:line`.
   - Read the actual code at that location.
   - If legitimate, edit the source in place to fix it.
   - If you disagree, push back in your response with reasoning; the user makes the final call.
   - **Critical** and **Major** findings block approval; you must either fix them or explicitly justify pushing back.
   - **Minor** and **Suggestion** are case-by-case — fix the low-cost ones, defer the rest if the user agrees.

4. **Turn 2+**: re-run the test suite, build a fresh test summary, and invoke the resume helper:
   ```
   export STATE_DIR=".claude/skills/codex-code-review/state"
   uv run ruff check . && uv run mypy && uv run pytest -q
   TEST_SUMMARY="ruff: clean | mypy: clean | pytest: <updated counts>"
   bash .claude/skills/codex-plan-review/scripts/resume.sh \
       --prompt-file .claude/skills/codex-code-review/prompts/resume.tpl \
       docs/1-plans/F_x.y.z_feature-name.plan.md \
       "$TEST_SUMMARY"
   ```
   Re-running tests each turn matters — a fix you applied for one finding may have broken something else. Codex sees the updated test status alongside the diff. Loop back to step 2.

5. **Iteration cap**: by default, stop after **5 rounds** even if not yet `APPROVED`. Surface to the user with a summary of remaining open findings and let them decide whether to push for another round, accept the current state, or request rework.

### No-plan target (hotfixes / unplanned work)

If the implementation has no `docs/1-plans/F_*.plan.md` (e.g., a hotfix landed without a plan), pass a short **free-form label** instead of a plan path. Anything is fine; the scripts sanitize it into a state-file key.

```
TARGET="hotfix-watertightness-edge-leak"
bash .claude/skills/codex-plan-review/scripts/start.sh \
    --prompt-file .claude/skills/codex-code-review/prompts/start.tpl \
    "$TARGET" "$TEST_SUMMARY"
```

The prompt template detects the no-plan case and adapts: instead of plan-conformance ("does the code implement the plan?"), Codex reviews against `docs/ARCHI.md` patterns and the change's stated intent (which you can put in `EXTRA_PROMPT` alongside the test summary). All other checklist sections still apply.

### After convergence — synthesize the final review

**Important — why synthesis is needed.** The shared scripts overwrite `state/<key>.review.txt` on every turn. The Turn-1 review is a full checklist; Turn-2+ reviews are *deltas* asked for by the resume prompt ("confirm prior findings addressed; flag new ones"). After 3 rounds, the state file holds only Turn 3's delta — typically something like "all prior findings addressed, no new issues, APPROVED", which is *not* a code review. Archiving that file directly would mislead future readers into thinking the change was waved through with zero findings.

The fix: one extra Codex call that asks for a **consolidated final review** covering every finding raised across the whole thread. Codex still has the thread context, so it can produce a single coherent review rendered against `.codex/skills/TRIP-3-review/cr-template.md`.

**Synthesize** (skip if the loop converged on Turn 1 — the state file already holds a full review):

```
export STATE_DIR=".claude/skills/codex-code-review/state"
bash .claude/skills/codex-plan-review/scripts/resume.sh \
    --prompt-file .claude/skills/codex-code-review/prompts/synthesize.tpl \
    docs/1-plans/F_x.y.z_feature-name.plan.md \
    "Today's date is YYYY-MM-DD"
```

(Pass today's date via the trailing positional arg so it lands in `{{EXTRA_PROMPT}}` and Codex doesn't have to guess.)

The synthesize prompt fills in the canonical CR skeleton from `cr-template.md` and ends with the line `PROMOTION_READY`. The state file is overwritten with this consolidated review. The **Version** placeholder (`<x.y.z>`) is deliberately left unfilled — Step 2 below resolves the version, and the promote step (Step 3) substitutes it in.

**Edge cases at synthesis time**:

- **One-round APPROVED on a small change**: the Turn-1 state file is already a full review. Skip the synthesize call.
- **Capped without APPROVED**: still run synthesize. Codex covers the open findings and the user's acceptance/override reasoning; verdict reflects "APPROVED with observations" or "NEEDS REVISION".
- **User explicitly skipped Codex**: no synthesize call. The CR file is hand-written at promote time (Step 3 below) with body "Code review skipped — change classed as trivial by user judgment".

> **Promotion deferred to Step 3.** The actual write to `docs/3-code-review/CR_wa_vx.y.z.md` requires the project week (`a`) and version (`x.y.z`), neither of which is known until Steps 1 and 2 below. The state file holds the consolidated review until then. See Step 3 for the promote action.

### Operating notes

- **Surface Codex's review verbatim** to the user each round, not just your interpretation. They want to see what the reviewer said.
- **Keep edits scoped to the addressed findings.** Don't bundle unrelated cleanups during the loop — that makes the next re-review noisy.
- **If Codex repeatedly raises the same finding** despite your edits, re-read it carefully — usually you addressed an adjacent concern, not the actual one.
- **Reset the thread** (`bash .claude/skills/codex-plan-review/scripts/reset.sh <plan-path>` with `STATE_DIR=".claude/skills/codex-code-review/state"` exported) only if the thread context has become genuinely confused. Resetting loses prior context and starts the loop over.
- **Don't run the loop on changes the user explicitly said "skip"** — respect their judgment.
- **Tests must pass before APPROVED.** The Codex prompt's approval gate requires `uv run pytest`, `uv run ruff check .`, and `uv run mypy` to be green. If they aren't, fix that first.

---

**ONLY after Codex review converges (or is skipped) and the user confirms "Yes, everything is complete"**, proceed with these steps:

### Step 1: Get Current Date/Week

Run this command to get date and project week:

```bash
date '+%d-%m-%Y %H:%M' && echo "Project week: $(( ( $(date +%s) - $(date -d '2026-04-27' +%s) ) / 604800 + 1 ))"
```

Use the project week in all subsequent steps.

### Step 2: Version Update

- If not already done in the plan phase, propose new SemVer version (x.y.z)
- Update `version = "x.y.z"` in `pyproject.toml` (the project's authoritative version field). Do not modify anything else in this file.
- `src/raysim/__init__.py` carries `__version__` for runtime introspection; update it to match.

### Step 3: Promote the Code Review

Now that `a` (project week, from Step 1) and `x.y.z` (version, from Step 2) are both known, write the consolidated review out of the state file into the canonical location.

1. **Locate the state file** for this implementation. The codex-code-review skill keys it on the target you used during the loop — typically the plan path. Compute the key the same way `_common.sh` does (sanitize the path: replace `/` with `__`, strip leading `/`):
   ```bash
   STATE_KEY="$(realpath docs/1-plans/F_x.y.z_feature-name.plan.md \
       | sed 's|^/||; s|/|__|g')"
   STATE_FILE=".claude/skills/codex-code-review/state/${STATE_KEY}.review.txt"
   ```

2. **Decide what to write**:
   - **If the synthesize step ran** (multi-round loop): the state file contains the consolidated review followed by a `PROMOTION_READY` line. Strip that sentinel.
   - **If the loop converged on Turn 1**: the state file contains the full Turn-1 review (no synthesis needed; no sentinel to strip).
   - **If the user explicitly skipped the Codex loop**: the state file is missing or empty. Write the CR file by hand using the skeleton in `.codex/skills/TRIP-3-review/cr-template.md`, body: "Code review skipped — change classed as trivial by user judgment." Verdict: `APPROVED with observations`.

3. **Substitute placeholders**. The synthesized review leaves the `<x.y.z>` Version placeholder unfilled — replace it with the actual version from Step 2. Other angle-bracket placeholders (Date, Files Reviewed, Plan, etc.) should already be filled in by Codex; if any remain, fill them yourself.

4. **Save** to `docs/3-code-review/CR_wa_vx.y.z.md` with `a` from Step 1 and `x.y.z` from Step 2.

5. **Verify**: open the resulting file and confirm there are no `<...>` placeholders left, no `PROMOTION_READY` sentinel, and the version line matches `pyproject.toml`.

The state file in `.claude/skills/codex-code-review/state/` is gitignored and stays as session debris; the committed `docs/3-code-review/CR_*.md` is the audit trail going forward.

### Step 4: Commit Message

Propose a one-line commit message.

### Step 5: Changelog File

Create `docs/2-changelog/wa_vx.y.z.md` (a=project week, x.y.z=version):

```markdown
# Changelog - Week a, DD-MM-YYYY, V. x.y.z

**Release Date**: Week a, DD-MM-YYYY at HH:MM
**Version**: x.y.z (previously x0.y0.z0)
**Object**: the commit message
**Code review**: <one of>
  - `docs/3-code-review/CR_wa_vx.y.z.md` (Codex loop, N rounds → APPROVED)
  - `docs/3-code-review/CR_wa_vx.y.z.md` (Codex loop capped at N rounds, M open findings accepted by user)
  - `docs/3-code-review/CR_wa_vx.y.z.md` (Codex loop skipped — trivial change)

## Changes

[Describe what changed]
```

The **Code review** line keeps the audit trail visible from the top-level changelog: every version states whether and how it was reviewed, and points at the `CR_*.md` for the full record. No silent gaps.

### Step 6: Changelog Table

Add entry on top of `docs/2-changelog/changelog_table.md`:

```markdown
| `x.y.z` | a | the commit message |
```

Also add a summary entry in the Changelog Summary section.

### Step 7: Architecture Update

1. Read fully @docs/ARCHI-rules.md
2. Update @docs/ARCHI.md following the rules
3. Run `bash .claude/skills/TRIP-compact/count-tokens.sh docs/ARCHI.md` to check token count

### Step 8: Tutorial

Create `docs/5-tuto/tuto_x.y.z.md` explaining the core principle introduced or exercised by this implementation. Pick *one* concept worth a focused write-up — not a re-summary of the diff.

**User context for tutorials**:

- Level: **Intermediate** (comfortable with Python basics; learning advanced)
- Learning focus: **Language fundamentals + Framework specifics + Architecture & patterns + Performance & optimization** (any combination is fair game; pick what's most relevant to the change)
- Style: **Balanced** (explanations with examples; not too terse, not exhaustive)

Good tutorial seeds for RaySim: the float32/64 boundary, the eps-gap correction derivation, why the stack accumulator is correct on nested solids, how the canonical-JSON serializer enforces bit-identity, the HEALPix equal-area property and why it lets us use unweighted means, embreex internals, log-cubic spline tradeoffs.

### Step 9: README Update

Update `README.md` with the new version number.
Also update relevant sections whenever needed.

---

**Warning: If ARCHI.md exceeds ~20,000 tokens**, warn the user:

> "ARCHI.md is at ~X tokens. Consider running `TRIP-compact` to reduce it before committing."

After completing all documentation steps, **use the `AskUserQuestion` tool** to ask:

- **Question**: "All documentation steps are complete. Ready to commit?"
- **Options**: "Yes, commit now" (proceed with git commit and tag), "Not yet" (review changes first)

**ONLY after user selects "Yes"**, proceed:

### Step 10: Commit

```bash
git add -A && git commit -m "<commit message from Step 4>"
```

**Important**: Only use the commit message. Do NOT add Co-Authored-By or any other trailer.

### Step 11: Tag

```bash
git tag vx.y.z
```
