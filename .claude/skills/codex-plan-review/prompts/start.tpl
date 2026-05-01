Read fully docs/ARCHI.md MVP_PLAN.md MVP_STEPS.md then review the planning document at `{{TARGET}}`.

Your job: identify correctness, coherence, and completeness issues that would block implementation.
Cite specific line numbers. Tag findings P1 (must fix) or P2 (should clarify). Prefer concrete fixes over vague critiques.

Important: when a plan explicitly states it intentionally changes a requirement from an existing
document (e.g., relaxing a gate, changing a default) AND includes that document in its update/to-do
list, that is not a finding — the plan IS the change request. Only flag it if the plan fails to
list the doc update or if the change creates an internal contradiction within the plan itself.

End your response with exactly one of these tags on its own line:
  APPROVED
  REQUEST_CHANGES
  NEEDS_REWORK

{{EXTRA_PROMPT}}
