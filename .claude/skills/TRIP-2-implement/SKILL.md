---
name: TRIP-2-implement
description: Implement a feature following TRIP plan
argument-hint: "plan file or feature to implement"
---

# Implementation Mode — RaySim

## Prerequisites

Read ALL lines of @docs/ARCHI.md before implementing.

## Task

Implement: $ARGUMENTS

---

## Step 0: Branch Evaluation

`AskUserQuestion`: "This involves [scope assessment]. Create a dedicated branch?"
Options: "Yes, create branch" (suggest `feat/[desc]` or `fix/[desc]`) / "No, stay on current branch"

Create branch if: multi-module, could break existing functionality, needs review, multi-session, or risky.

---

## Implementation Rules

Apply DRY, KISS. Follow existing codebase patterns. Add comments only for non-obvious logic.

---

## Implementation Phase

Implement following the plan or task description. Cross corresponding checkboxes in the plan to-do list as you go.

---

## Codex Code Review

After implementation, before user sign-off, run the Codex code review loop.

### Pre-step: run tests

Codex can't execute tests. Run them and pass the summary:

```bash
uv run ruff check . 2>&1 | tee /tmp/_trip2-lint.txt
uv run mypy          2>&1 | tee /tmp/_trip2-mypy.txt
uv run pytest -q     2>&1 | tee /tmp/_trip2-pytest.txt
```

Fix failures before starting the loop. Format summary: `ruff: clean | mypy: clean | pytest: N passed, 0 failed, M skipped`

### Confirm

`AskUserQuestion`: "Implementation looks done. Run Codex code review against the plan?"
Options: "Yes, run Codex review" (recommended) / "Skip Codex" / "Cap iterations at N"

### Loop

Always export before invoking shared scripts:

```bash
export STATE_DIR=".claude/skills/codex-code-review/state"
```

1. **Start**:
   ```bash
   bash .claude/skills/codex-plan-review/scripts/start.sh \
       --prompt-file .claude/skills/codex-code-review/prompts/start.tpl \
       <plan-path> "$TEST_SUMMARY"
   ```
   For unplanned work (no `F_*.plan.md`), pass a free-form label instead of a plan path.

2. **Parse trailing tag**: `APPROVED` → synthesize. `NEEDS_REWORK` → surface to user. `REQUEST_CHANGES` → continue.

3. **Address findings** — quote each with `file:line`, read the actual code, fix legitimate ones, push back on incorrect ones. Critical/Major block approval; Minor/Suggestion are case-by-case.

4. **Resume** (re-run tests first, build fresh summary):
   ```bash
   bash .claude/skills/codex-plan-review/scripts/resume.sh \
       --prompt-file .claude/skills/codex-code-review/prompts/resume.tpl \
       <plan-path> "$TEST_SUMMARY"
   ```
   Loop to step 2.

5. **Cap at 5 rounds** (or user-specified). Surface remaining findings.

### Synthesize

Skip if loop converged on Turn 1 (state file already holds full review).

Turn-N state files hold only that turn's delta. After multi-round convergence, produce a consolidated review:

```bash
bash .claude/skills/codex-plan-review/scripts/resume.sh \
    --prompt-file .claude/skills/codex-code-review/prompts/synthesize.tpl \
    <plan-path> "Today's date is YYYY-MM-DD"
```

Outputs `PROMOTION_READY` sentinel. `<x.y.z>` Version placeholder left unfilled (resolved in Step 2 below).

Edge cases:
- **Capped without APPROVED**: still synthesize; Codex notes open findings.
- **User skipped Codex**: no synthesis. Write CR manually: "Code review skipped — trivial change."

### Operating notes

Surface reviews verbatim. Keep edits scoped. If Codex repeats a finding, re-read carefully — you likely addressed an adjacent concern. Reset thread only if context is confused. Tests must pass before APPROVED.

---

## Post-Implementation

After Codex converges (or is skipped):

`AskUserQuestion`: "Is the implementation complete?"
Options: "Yes, everything is complete" / "No, remaining items"

**Only after "Yes"**, proceed:

### Step 1: Date/Week

```bash
date '+%d-%m-%Y %H:%M' && echo "Project week: $(( ( $(date +%s) - $(date -d '2026-04-27' +%s) ) / 604800 + 1 ))"
```

### Step 2: Version Update

Propose SemVer version. Update `version` in `pyproject.toml` and `__version__` in `src/raysim/__init__.py`.

### Step 3: Promote Code Review

Now that week (`a`) and version (`x.y.z`) are known:

1. Compute state file path:
   ```bash
   STATE_KEY="$(realpath <plan-path> | sed 's|^/||; s|/|__|g')"
   STATE_FILE=".claude/skills/codex-code-review/state/${STATE_KEY}.review.txt"
   ```

2. Content source:
   - **Multi-round loop**: state file has synthesized review + `PROMOTION_READY`. Strip sentinel.
   - **Turn 1 convergence**: state file has full review already.
   - **Skipped Codex**: write CR from `.codex/skills/TRIP-3-review/cr-template.md` with body "Code review skipped — trivial change." Verdict: `APPROVED with observations`.

3. Replace `<x.y.z>` with actual version. Fill any remaining `<...>` placeholders.

4. Save to `docs/3-code-review/CR_wa_vx.y.z.md`.

5. Verify: no `<...>` placeholders, no `PROMOTION_READY`, version matches `pyproject.toml`.

### Step 4: Commit Message

Propose a one-line commit message.

### Step 5: Changelog

Create `docs/2-changelog/wa_vx.y.z.md`:

```markdown
# Changelog - Week a, DD-MM-YYYY, V. x.y.z

**Release Date**: Week a, DD-MM-YYYY at HH:MM
**Version**: x.y.z (previously x0.y0.z0)
**Object**: the commit message
**Code review**: `docs/3-code-review/CR_wa_vx.y.z.md` (Codex loop, N rounds → verdict)

## Changes
[Describe what changed]
```

### Step 6: Changelog Table

Add to top of `docs/2-changelog/changelog_table.md`:
```markdown
| `x.y.z` | a | the commit message |
```
Also add a summary entry in the Changelog Summary section.

### Step 7: Architecture Update

1. Read fully @docs/ARCHI-rules.md
2. Update @docs/ARCHI.md following the rules
3. Run `bash .claude/skills/TRIP-compact/count-tokens.sh docs/ARCHI.md`

**If ARCHI.md exceeds ~20,000 tokens**, warn user to run `TRIP-compact`.

### Step 8: Tutorial

Create `docs/5-tuto/tuto_x.y.z.md` — one concept worth a focused write-up, not a diff summary.

User context: intermediate Python, balanced style. Any focus: language fundamentals, framework specifics, architecture, performance.

Good seeds: float32/64 boundary, eps-gap derivation, stack accumulator correctness, canonical-JSON bit-identity, HEALPix equal-area property, embreex internals, log-cubic spline tradeoffs.

### Step 9: README

Update `README.md` version number and relevant sections.

---

`AskUserQuestion`: "All documentation complete. Ready to commit?"
Options: "Yes, commit now" / "Not yet"

### Step 10: Commit

```bash
git add -A && git commit -m "<commit message>"
```

No Co-Authored-By or other trailers.

### Step 11: Tag

```bash
git tag vx.y.z
```
