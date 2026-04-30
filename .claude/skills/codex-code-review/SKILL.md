---
name: codex-code-review
description: Iteratively review a code change with the Codex CLI against the implementation plan it claims to satisfy. The first invocation starts a fresh Codex session keyed on the plan path; subsequent invocations resume the same thread so Codex remembers prior findings and only flags incremental issues. Codex inspects the change set itself via `git status -s` and `git diff HEAD` (working-tree state vs last commit) — review fires *before* the commit so iterations land in one clean commit. Use when the user asks to "review the code with codex", "get a codex code review", "second-opinion this implementation", or at the end of a TRIP-2-implement run before final user sign-off.
argument-hint: "<plan-path> [optional extra context for codex] | reset <plan-path> | show <plan-path>"
---

# Codex Code Review Skill

Drive an iterative code review using the Codex CLI as the second
opinion on a freshly-implemented change set. Codex reads the
implementation plan, runs `git status` / `git diff` itself to see
what was changed, and produces a checklist-driven review adapted from
`docs/3-code-review/` standards (functional requirements, code
quality, architectural compliance, determinism, numerical precision,
stack accumulator invariants, material physics scope, error handling,
performance, optional-backend hygiene).

The skill **does not request a per-iteration `CR_*.md` review file** —
review output stays in the per-target state file under this skill's
own `state/` directory. The final review record can be promoted to
`docs/3-code-review/CR_wa_vx.y.z.md` after the loop converges, but
that's an end-of-loop step (see "After convergence" below), not a
per-turn artifact.

State (thread id, last review text, raw event log) is persisted under
`.claude/skills/codex-code-review/state/<sanitized-plan-path>.{thread,review.txt,events.ndjson}`
so multiple reviews can be in flight concurrently and don't collide
with `codex-plan-review` state for the same plan.

The shell helpers under `.claude/skills/codex-plan-review/scripts/`
are shared between both skills; this skill provides its own prompt
templates and exports its own `STATE_DIR` before invoking them.

## Arguments

`$ARGUMENTS` takes one of these shapes:

- `<target>` — auto: start a new review session keyed on the target
  if no thread exists, otherwise resume the existing one. The
  *change set* is whatever `git diff HEAD` shows — Codex resolves
  it itself.
  - **`<target>` is usually the path to the implementation plan**
    (e.g. `docs/1-plans/F_0.1.0_*.plan.md`). Codex reads it and
    reviews against plan-conformance + the rest of the checklist.
  - **`<target>` may also be a free-form label** (e.g.
    `hotfix-watertightness-edge-leak`) when the work was unplanned
    (hotfix without a plan, refactor cleanup, etc.). The keying is
    sanitized; any string is accepted. The prompt template detects
    the no-plan case and skips the plan-conformance criterion —
    every other checklist item still applies.
- `reset <target>` — drop the per-target code-review state so the
  next call starts a fresh Codex thread.
- `show <target>` — re-display the most recent review without
  calling Codex.

## What you (Claude) should do

The shared scripts live under
`.claude/skills/codex-plan-review/scripts/` but write to *this*
skill's `state/` when `STATE_DIR` is set. Always export `STATE_DIR`
before invoking them.

```
export STATE_DIR=".claude/skills/codex-code-review/state"
```

1. **Parse `$ARGUMENTS`.** Extract the action keyword (`reset` /
   `show`) if present, otherwise default to *auto*. The first
   non-flag token is the plan path; remaining tokens are extra
   context.

2. **For `auto` action**, check whether
   `.claude/skills/codex-code-review/state/<key>.thread` exists
   (try `start.sh` first; exit code `2` means thread exists, fall
   through to `resume.sh`):

   - **No thread file** → run:
     ```
     export STATE_DIR=".claude/skills/codex-code-review/state"
     bash .claude/skills/codex-plan-review/scripts/start.sh \
         --prompt-file .claude/skills/codex-code-review/prompts/start.tpl \
         <plan-path> [extra context]
     ```
   - **Thread file exists** → run:
     ```
     export STATE_DIR=".claude/skills/codex-code-review/state"
     bash .claude/skills/codex-plan-review/scripts/resume.sh \
         --prompt-file .claude/skills/codex-code-review/prompts/resume.tpl \
         <plan-path> [extra context]
     ```

3. **For `reset` action**, run:
   ```
   export STATE_DIR=".claude/skills/codex-code-review/state"
   bash .claude/skills/codex-plan-review/scripts/reset.sh <plan-path>
   ```

4. **For `show` action**, run:
   ```
   export STATE_DIR=".claude/skills/codex-code-review/state"
   bash .claude/skills/codex-plan-review/scripts/show.sh <plan-path>
   ```

5. **After Codex returns**, parse the trailing tag:

   - `APPROVED` — convergence; the implementation passes Codex's
     checklist. Tell the user, propose the post-convergence steps
     below.
   - `REQUEST_CHANGES` — Codex has Critical / Major / Minor /
     Suggestion findings. Engage critically — not every Codex finding
     is correct. For each:
       1. Read it carefully against the actual code.
       2. If legitimate, edit the source file in place to fix it.
       3. If you disagree, push back in your response with reasoning;
          the user makes the final call.
     Surface the full Codex review verbatim to the user before
     starting edits, then propose your fix list and let the user
     confirm.
   - `NEEDS_REWORK` — structural issues; raise with the user before
     mass-editing.

6. **Re-run via `resume`** after addressing findings. Codex remembers
   the prior round and re-evaluates only the deltas plus any new
   issues introduced by your fixes.

## Diff visibility

Codex inspects the change set via `git status` / `git diff` against
the merge base. With `--sandbox read-only`, those commands run fine
(read-only workspace operations).

If Codex reports it cannot run those commands in your environment
(rare, but possible if the sandbox is more restrictive than expected),
fall back to passing the diff inline:

```
DIFF="$(git diff --stat HEAD; echo '---'; git diff HEAD)"
bash .claude/skills/codex-plan-review/scripts/start.sh \
    --prompt-file .claude/skills/codex-code-review/prompts/start.tpl \
    <plan-path> "$DIFF"
```

The diff lands in the `{{EXTRA_PROMPT}}` placeholder of the prompt.

## After convergence (APPROVED)

When the loop converges, propose these end-of-loop steps to the user:

1. **Promote the final review to `docs/3-code-review/`**: copy the
   per-target `state/<key>.review.txt` content into
   `docs/3-code-review/CR_wa_vx.y.z.md` using the template at the
   bottom of `.codex/skills/TRIP-3-review/SKILL.md`. This is the
   archival, human-readable record. Per-turn iteration files stay in
   `state/` and don't get committed.
2. Continue with the regular TRIP-2-implement post-implementation
   steps (version bump, changelog entry, README update, commit,
   tag).

The user may opt to skip step 1 if the review didn't surface
anything noteworthy.

## Operational notes

- Codex runs with `--sandbox read-only`. Safe to invoke autonomously.
- Network failures appear in `*.events.ndjson.stderr`. On failure,
  run `reset.sh` and try again.
- The `--last` selector is **not** used. Thread ids are persisted
  per-plan-path so concurrent codex activity doesn't poison the
  thread.
- This skill and `codex-plan-review` use **separate** state
  directories — sharing the plan path as a key is fine because the
  state files live in different directories.
- Extra context is verbatim, substituted into the `{{EXTRA_PROMPT}}`
  placeholder. Keep it short (e.g. "the watertightness gate landed
  in `geom/watertightness.py:120-180` — verify the override flow").

## Convergence loop shape

```
turn 1: start.sh --prompt-file prompts/start.tpl <plan>
            → REQUEST_CHANGES, Critical: A; Major: B C
        you address A B C in source files
turn 2: resume.sh --prompt-file prompts/resume.tpl <plan>
            → REQUEST_CHANGES, A and B addressed,
              Minor: C still partial; Suggestion: D
        you address C and (optionally) D
turn 3: resume.sh --prompt-file prompts/resume.tpl <plan>
            → APPROVED
        promote review to docs/3-code-review/, continue TRIP-2
```
