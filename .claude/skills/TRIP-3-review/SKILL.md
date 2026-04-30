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
4. @.codex/skills/TRIP-3-review/checklist.md - the **single source of truth** for review criteria, severity classification, and the approval gate. The codex-driven review path (`.claude/skills/codex-code-review`) reads the same file, so the two review surfaces stay aligned by construction.

---

## How to apply the checklist

Walk every section of `checklist.md` against the code change in scope. Tick each item that passes. Items that don't pass become findings, classified by the severity scale in the same file. Approval requires the "Review Completion Criteria (Approval Gate)" at the bottom of `checklist.md` to be satisfied.

Do **not** copy the checklist into your review output — link to it. The CR file template below has its own short summary checklist.

---

## Post-Review: Create Review File

After completing the review, create a summary file in `docs/3-code-review/`.

> Note for the codex-code-review iteration loop: this section is for the human-driven TRIP-3 review path only. The codex iteration loop handles archival via its `synthesize.tpl` step + the TRIP-2 "After convergence — synthesize, then promote" flow, *not* by generating a CR file per turn. If you are running under that loop, ignore this section.

**File naming**: `CR_wa_vx.y.z.md` (a=project week, x.y.z=version)

**Format**: render the canonical skeleton from `@.codex/skills/TRIP-3-review/cr-template.md`. That file is the single source of truth for the CR markdown structure — both this human-driven path and the Codex iteration loop's synthesize step write output that conforms to it, so a future reader can compare them apples-to-apples.

Workflow:

1. Open `.codex/skills/TRIP-3-review/cr-template.md` and copy the markdown block out (the part between the triple backticks).
2. Save it to `docs/3-code-review/CR_wa_vx.y.z.md`.
3. Replace every `<angle-bracket placeholder>` with concrete content from your review.
4. Tick the boxes (`[x]`) for the 10 checklist items that passed cleanly; leave unchecked with a one-line caveat for the rest.

**Important:** every checklist item must be ticked or annotated. If you didn't check a point for any reason, add a one-line caveat explaining why. A silent unchecked box is a red flag for a future reader.
