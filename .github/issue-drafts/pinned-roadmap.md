---
title: "Roadmap: retrieval experiments → backend decision (ADR 0007)"
labels: ["roadmap"]
pinned: true
---

## Where we are

**v0.12.2** measured the first retrieval-v1 lexical baseline. The benchmark has 18 frozen queries, graded relevance judgments, a deterministic offline runner, and committed reports. Key findings:

| metric | value |
|---|---|
| Exact-span hit rate | 1.000 |
| MRR (answerable) | 0.938 |
| Recall@5 | 0.938 |
| No-answer correctness | 0.000 (both no-answer queries return false support) |
| False-support rate | 1.000 |

The lexical retriever is strong on exact lookup and character-overlapping paraphrase. It is weak on **broad thematic recall** and **no-answer discrimination**.

## What comes next (in order)

### 1. Lexical confidence threshold experiment ✅

> Branch: `experiment/retrieval-threshold-baseline`

A post-retrieval cutoff: if the top score is below a threshold, return no support. Results (committed):

| threshold | no-answer correct | false-support | recall@5 | regressions |
|---|---|---|---|---|
| baseline | 0.000 | 1.000 | 0.938 | — |
| **t=2** | **1.000** | **0.000** | **0.938** | **none** |
| t=5 | 1.000 | 0.000 | 0.859 | q007, q010 |

**Finding:** threshold=2 fixes both no-answer queries with zero regression. The score gap is clean (no-answer top-1 = 1, minimum answerable top-1 = 4).

### 2. BM25-style lexical ranking experiment ⬜

> Branch: `experiment/retrieval-bm25-stdlib`

Test whether a term-frequency / inverse-document-frequency ranking (BM25-style, stdlib-only) improves **broad thematic recall** (the baseline's other weakness) without losing provenance and stable identity.

### 3. ADR 0007 — backend decision ⬜

> Only after at least two candidates are measured.

Compare all candidates against the v0.12.2 baseline on the full metric set (recall, precision, nDCG, citation fidelity, no-answer correctness, false-support, latency, dependency footprint). Possible outcomes:

1. Keep the current lexical retriever (acceptable — the baseline is strong on its core job).
2. Add a conservative confidence threshold.
3. Adopt BM25-style local lexical ranking.
4. Defer until the corpus grows.

Dense/vector/RAG is **not justified unless** lexical methods fail materially on the benchmark.

## What is NOT on the roadmap

- No vector embeddings, no external dependencies, no RAG service — until benchmark evidence justifies it.
- No edition-backed assurance — that is tied to A2 corpus provenance work, not retrieval quality.
- No changes to the retrieval envelope contract — the contract is fixed; only the backend behind it may change.

## How to help

- **Add corpus records** — more records improve benchmark coverage. See #good-first-issue.
- **Add benchmark queries** — more queries improve statistical power before the backend decision.
- **Review relevance judgments** — the baseline is a single-curator pass; a second independent judge strengthens the decision gate.
- **Propose a candidate** — if you have a stdlib-friendly ranking approach, open an experiment branch.

See [Retrieval Benchmark v1](../../docs/benchmarks/retrieval-v1.md) for the full design and decision gates.
