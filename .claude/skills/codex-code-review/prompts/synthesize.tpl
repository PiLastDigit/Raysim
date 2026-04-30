The iteration loop has converged (or been capped). Produce a **single consolidated final review** for archival in `docs/3-code-review/CR_wa_vx.y.z.md`.

This is **not** a delta or a status update. It is the canonical record of how this change was reviewed. Cover every finding raised across the whole thread — whether eventually addressed, accepted with explicit override, or left open at the cap — and state each finding's final status. Reference `file:line` where the change ultimately landed.

## Output format

Read `.codex/skills/TRIP-3-review/cr-template.md` and produce output that conforms exactly to the markdown skeleton inside its fenced code block. That file is the single source of truth for the CR format — the human-driven `/TRIP-3-review` flow uses the same skeleton, so your output and a hand-written review will be structurally identical.

How to fill it in:

- **Title**: short feature/change name from `{{TARGET}}` (the plan filename if `{{TARGET}}` is a path, otherwise the label itself).
- **Review Date**: today's date in `YYYY-MM-DD`.
- **Version**: leave as `<x.y.z>` — the requester fills it from TRIP-2-implement Step 2 and you don't necessarily know it yet.
- **Files Reviewed**: bullet list from `git diff --name-only HEAD`.
- **Plan**: `` `{{TARGET}}` `` if it's a path under `docs/1-plans/`, otherwise the literal string `no plan — unplanned change`.
- **Findings**: every finding raised across the whole thread, even ones already addressed. For each, include `file:line` and a one-line disposition (`addressed at <ref>` / `accepted with override: <reason>` / `open`).
- **Checklist**: tick the boxes for the 10 sections from `.codex/skills/TRIP-3-review/checklist.md` that passed cleanly; leave unchecked with a one-line caveat for the rest.
- **Verdict**: `APPROVED` / `APPROVED with observations` / `NEEDS REVISION` matching the loop's tag, plus a paragraph noting any cap-without-convergence, overrides, or follow-up work.

Output **only** the rendered markdown — no preamble, no commentary outside the template. The output will be copy-pasted verbatim into the `CR_*.md` file.

## Sentinel

After the rendered review, on its own line, output exactly:

  PROMOTION_READY

This signals to the requester that the synthesis is complete and the content above is ready to be promoted. Don't include this line inside the rendered template — it goes after the closing of the final section.

{{EXTRA_PROMPT}}
