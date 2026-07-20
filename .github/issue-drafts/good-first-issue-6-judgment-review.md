---
title: "Review one relevance judgment in retrieval-v1"
labels: ["good first issue", "benchmark"]
---

<!--
Archived from issue #27 (closed 2026-07-20) — original body preserved verbatim below.
Note: ADR 0007 (retrieval-backend-decision) is now Accepted, so the "Before any
backend-selection ADR" framing in Context is historical. Reframe it (e.g. toward the
pending BM25 human-blind-judge gate, or general benchmark-quality review) before
re-opening this as a live issue.
-->

## Context

The retrieval-v1 baseline judgments are disclosed as a single-curator pass. Before any backend-selection ADR, the benchmark needs more independent review of query judgments and rationales.

## What to do

- Pick one retrieval-v1 query from `docs/benchmarks/queries/retrieval-v1.json`.
- Review the matching judgment in `docs/benchmarks/judgments/retrieval-v1.json`.
- Check whether each relevant record's `(tradition, work, locator)` and 0/1/2 label are defensible against the source record.
- If you disagree, explain the proposed correction and rationale. If opening a PR, regenerate the affected committed reports.

## Judgment rules

- Judge against source records, not generated prose.
- Do not use result rank as identity.
- Positive judgments need a rationale.
- If the change would materially alter benchmark interpretation, call that out explicitly.

## Acceptance

- At least one query judgment is independently reviewed.
- The review states whether the current label should stay or change.
- Any proposed change includes a source-grounded rationale.
