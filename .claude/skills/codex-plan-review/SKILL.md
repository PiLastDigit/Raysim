---
name: codex-plan-review
description: Iteratively review a planning document with the Codex CLI. The first invocation starts a fresh Codex session and captures its thread_id; subsequent invocations resume the same thread so Codex remembers prior findings and only flags incremental issues. Use when the user asks to "review the plan with codex", "get a codex plan review", "second-opinion this plan", or in TRIP-1-plan iteration loops where back-and-forth review converges on APPROVED.
argument-hint: "<plan-path> [optional extra context for codex] | reset <plan-path> | show <plan-path>"
---

# Codex Plan Review Skill

Drive an iterative review of a planning document using the Codex CLI as the second opinion. State (thread id, last review text, raw event log) is persisted per-plan under `.claude/skills/codex-plan-review/state/<sanitized-plan-path>.{thread,review.txt,events.ndjson}` so multiple plans can be in review concurrently and the same Codex thread is resumed across turns.

The companion skill `codex-code-review` reuses the same scripts for post-implementation reviews. Both skills share the helpers under `.claude/skills/codex-plan-review/scripts/` and load skill-specific prompt templates via the `--prompt-file` flag.

## Arguments

`$ARGUMENTS` takes one of these shapes:

- `<plan-path>` — auto: start a new review session if no thread exists, otherwise resume the existing one. Optional trailing free-text is appended to the prompt as additional context.
- `reset <plan-path>` — drop the per-plan state so the next call starts a fresh Codex thread.
- `show <plan-path>` — re-display the most recent review without calling Codex (useful when the conversation has scrolled past).

## What you (Claude) should do

1. **Parse `$ARGUMENTS`.** Extract the action keyword (`reset` / `show`) if present, otherwise default to *auto*. The remaining first token is the plan path; remaining tokens (if any) are extra context for Codex.

2. **For `auto` action**, check whether `.claude/skills/codex-plan-review/state/<key>.thread` exists for the plan (the `_common.sh` `thread_file` helper computes the key — but you don't need to compute it yourself; just call the scripts):

   - **No thread file** → run:
     ```
     bash .claude/skills/codex-plan-review/scripts/start.sh \
         --prompt-file .claude/skills/codex-plan-review/prompts/start.tpl \
         <plan-path> [extra context]
     ```
   - **Thread file exists** → run:
     ```
     bash .claude/skills/codex-plan-review/scripts/resume.sh \
         --prompt-file .claude/skills/codex-plan-review/prompts/resume.tpl \
         <plan-path> [extra context]
     ```

   The simplest test from your side: try `start.sh` first; it exits with code `2` and a clear message if a thread already exists. On exit code 2, fall through to `resume.sh`. Or check the state file yourself with `test -f` first — either is fine.

3. **For `reset` action**, run `bash .claude/skills/codex-plan-review/scripts/reset.sh <plan-path>`.

4. **For `show` action**, run `bash .claude/skills/codex-plan-review/scripts/show.sh <plan-path>`.

5. **After Codex returns**, read its review (the scripts already cat it to stdout, so the Bash output is the review). Parse the trailing tag:

   - `APPROVED` — convergence; tell the user the plan passed Codex review.
   - `REQUEST_CHANGES` — Codex wants edits. Treat each finding as a review comment you should address by editing the plan file. Don't blindly apply every suggestion — engage critically: assess whether each finding is legitimate, push back on ones that aren't, fix the ones that are. After your edits, the user can re-trigger this skill to get an incremental re-review.
   - `NEEDS_REWORK` — material issues; raise them with the user before mass-editing.

6. **Surface the review to the user verbatim.** They want to see what Codex said, not just your interpretation. Then propose your fix list and let them confirm before you start editing.

## Operational notes

- Codex runs with `--sandbox read-only` so it can read repo files but never writes. Safe to invoke autonomously.
- Network failures (Codex backend, WSL DNS) sometimes appear in the per-plan `*.events.ndjson.stderr` file. The scripts surface stderr tails on failure. If a session start fails partway, run `reset.sh <plan>` and try again.
- The `--last` selector is **not** used — explicit thread ids are captured from the `thread.started` event and persisted per-plan, so unrelated Codex activity in the same cwd doesn't poison the review thread.
- Extra context appended to the prompt is verbatim — keep it short and factual (e.g. "focus on the gating semantics in §B1.6", "the prior reviewer flagged X — verify it's resolved"). It is substituted into the `{{EXTRA_PROMPT}}` placeholder of the prompt template.

## Convergence loop shape (for reference)

```
turn 1: start.sh --prompt-file prompts/start.tpl <plan>
            → REQUEST_CHANGES, findings A B C
        you address A B C in plan
turn 2: resume.sh --prompt-file prompts/resume.tpl <plan>
            → REQUEST_CHANGES, A and B addressed,
              C stale, new finding D
        you address C and D
turn 3: resume.sh --prompt-file prompts/resume.tpl <plan>
            → APPROVED
        done.
```

The Codex thread accumulates context across turns, so each re-review is incremental rather than re-evaluating from scratch.
