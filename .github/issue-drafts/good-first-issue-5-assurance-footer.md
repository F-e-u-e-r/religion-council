---
title: "Improve assurance footer wording for end users"
labels: ["good first issue", "docs", "enforcement"]
---

## Context

When `debate_finalize` runs in strict mode, an **assurance footer** is appended to the response. It summarizes how many authority claims were curated-snapshot-verified vs. denied, and always includes an interpretation limitation.

The current wording (`orchestrator/assurance_footer.py`) is technically accurate but reads like a developer log, not a user-facing trust signal. Example:

```
Authority: 1 curated-snapshot-verified · 0 denied
Interpretation: not source text — instruction-bounded, not machine-verified
```

## What to do

- Propose clearer wording that a non-technical user (e.g. a theology student, a curious reader) can understand.
- The footer must still convey: (1) how many claims were machine-verified, (2) that interpretation prose is not verified, (3) no false assurance.
- Keep it to 2-3 lines max.
- Run `python3 -m unittest tests.test_assurance_footer -v` — the tests assert structural invariants, not exact wording, so rewording should pass.

## Constraints

- Do not remove the interpretation limitation — it is a non-removable safety property.
- Do not claim edition-backed assurance — the current tier is curated-snapshot only.
