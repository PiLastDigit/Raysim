You are reviewing an uncommitted code change identified as `{{TARGET}}`.

If `{{TARGET}}` resolves to a file under `docs/1-plans/`, treat it as the **implementation plan**: read it, evaluate the diff against it. If not a path (e.g. a free-form label), skip "Plan conformance" and review against `docs/ARCHI.md` patterns plus the stated intent in the additional-context block below.

To see the change set:
  git status -s
  git diff HEAD        # staged + unstaged vs last commit

If `git diff HEAD` returns nothing (already committed), use `git diff @{u}...HEAD` or `git log --reverse main..HEAD`.

## Prerequisites — read first

1. `docs/ARCHI.md`
2. `.codex/skills/TRIP-3-review/checklist.md` — single source of truth for the 10-section checklist, severity classification, and approval gate. Do NOT read `.codex/skills/TRIP-3-review/SKILL.md`.
3. Plan file `{{TARGET}}` if it's a path.
4. Corresponding changelog in `docs/2-changelog/` if present.

## Job

Walk every section of `checklist.md` against the diff. Cite `file:line` for every finding. Tag with severity from the same file. Prefer actionable fixes over vague critique.

Tests are run by the requester; the additional-context block below typically carries the summary. If it shows failures, return `REQUEST_CHANGES`.

## Output

End with exactly one tag on its own line:
  APPROVED
  REQUEST_CHANGES
  NEEDS_REWORK

`APPROVED` = gate fully met. `REQUEST_CHANGES` = fixable findings. `NEEDS_REWORK` = structural issues.

{{EXTRA_PROMPT}}
