# Branch protection — `main`

Configured via GitHub Rulesets (2026-06-26).

## Active rules

| Rule | Setting |
|---|---|
| Force push | blocked |
| Branch deletion | blocked |
| Required status checks | `test (3.9)`, `test (3.11)` must pass |
| Up-to-date branch | required before merge |
| Require PR review | 1 approving review (admin bypass: always) |

## Bypass

Repository admins may use GitHub's bypass mechanism for maintainer-owned changes; external contributors still require review.

## Why these choices

- **Force push blocked** — the repo contains frozen contracts (ADR 0006), a frozen benchmark (retrieval-v1), safety-routing policy, and curated corpus with rights provenance. Rewriting history could silently break any of these.
- **Both Python versions required** — 3.9 is the project's floor (macOS system Python); 3.11 is the current target. Gating on only one lets stdlib or syntax regressions slip through.
- **PR review with admin bypass** — gates external contributions while preserving a practical solo-maintainer workflow for maintainer-owned changes.
