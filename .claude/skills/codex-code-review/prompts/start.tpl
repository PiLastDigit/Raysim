You are reviewing a code change that has just been written but is **not yet committed**. The change is identified as `{{TARGET}}`.

If `{{TARGET}}` is a path that resolves to a file under `docs/1-plans/`, treat it as the **implementation plan** the change must conform to: read it first, then evaluate the diff against it.

If `{{TARGET}}` is *not* a path (e.g. a free-form label like `hotfix-watertightness-edge-leak`), the work was unplanned. In that case skip the "Plan conformance" criterion and review against `docs/ARCHI.md` patterns plus the change's stated intent (which the requester may have placed in the additional-context block at the bottom of this prompt). Every other checklist criterion still applies.

To see the change set, run these commands yourself:

  git status -s        # list of files added / modified / deleted
  git diff HEAD        # unified diff of every working-tree change
                       # (covers staged AND unstaged — single command)

`git diff HEAD` is the right command (not `git diff` alone, which misses staged changes; not `git diff main...HEAD`, which misses the uncommitted working tree). The working tree is what's about to be committed, so it's what you're reviewing.

If `git diff HEAD` returns nothing, the change has already been committed — fall back to `git diff @{u}...HEAD` (or `git log --reverse main..HEAD` to find the commits introduced on this branch) and review those.

## Prerequisites — read these files first

1. `docs/ARCHI.md` — the source-of-truth architecture; verify compliance.
2. `.codex/skills/TRIP-3-review/checklist.md` — the **single source of truth** for the systematic review checklist (10 sections), the issue severity classification (Critical / Major / Minor / Suggestion), and the approval gate. Apply every criterion in this file against the diff. If you change anything, the same change applies to the human-driven TRIP-3 review path automatically — it reads the same file.
3. The plan file `{{TARGET}}` if it is a path — the design the implementation should match.
4. The corresponding changelog entry in `docs/2-changelog/` if one was landed alongside the code.

**Important — do *not* read `.codex/skills/TRIP-3-review/SKILL.md`.** That file contains the human-driven review's "Post-Review: Create Review File" template, which would mislead you into producing a `CR_*.md` file per turn. The codex iteration loop archives via a separate synthesis step *after* convergence — never per-turn. Stick to `checklist.md`.

## Your job

Walk every section of `.codex/skills/TRIP-3-review/checklist.md` against the code change in scope. Cite specific `file:line` references for every finding. Tag each finding with one of the four severity levels from the same file. Prefer concrete, actionable fixes over vague critique.

The "Review Completion Criteria (Approval Gate)" at the bottom of `checklist.md` is what gates an `APPROVED` verdict. Tests are run by the requester (you cannot execute `pytest`); the additional-context block at the bottom of this prompt typically carries the test summary (`ruff: clean | mypy: clean | pytest: N passed, M failed`). If the test summary shows failures, do not return `APPROVED` — return `REQUEST_CHANGES` with the failures called out.

## Output format

End your response with exactly one of these tags on its own line:

  APPROVED
  REQUEST_CHANGES
  NEEDS_REWORK

Use `APPROVED` only when the approval gate from `checklist.md` is fully met.
Use `REQUEST_CHANGES` for fixable findings.
Use `NEEDS_REWORK` when the implementation has structural issues that warrant a conversation, not mechanical fixes.

{{EXTRA_PROMPT}}
