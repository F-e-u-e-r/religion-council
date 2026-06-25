---
title: "Add a benchmark query for a gap the lexical baseline misses"
labels: ["good first issue", "benchmark"]
---

## Context

The retrieval-v1 benchmark has 18 frozen queries across 8 categories. The lexical baseline (v0.12.2) scores well on exact quotes and locators but poorly on:

- **Broad thematic queries** (q010 "人應該如何面對死亡" retrieves only 1 of 4 relevant records)
- **No-answer discrimination** (now addressable with threshold=2, but only 2 no-answer probes exist)

More queries improve the benchmark's statistical power before the backend-selection decision (ADR 0007).

## What to do

1. Draft a query following the schema in `docs/benchmarks/queries/retrieval-v1.json` (use it as a template, not an edit target).
2. Draft the corresponding judgment following `docs/benchmarks/judgments/retrieval-v1.json` — every positive label (relevance ≥ 1) needs a `rationale`.
3. Pick one of the existing categories or propose a new one.
4. Open an issue or PR proposing the query — the maintainer will coordinate the retrieval-v2 version bump, new fixture files, and report regeneration.

## Query ideas (pick one or propose your own)

- A **cross-lingual** query in English against the Chinese corpus (currently only romanized Sanskrit/Arabic are tested)
- A **no-answer** query on a clearly off-corpus modern topic (e.g. space exploration, cooking recipes) — more no-answer probes strengthen the threshold experiment
- A **cross-tradition** query on a shared theme like "forgiveness" or "the nature of the self"
- A **paraphrase** query that rephrases a known passage using entirely different vocabulary

## Important

Adding a query changes the frozen query set. Per the benchmark spec, this mints **retrieval-v2** — the query set defines the benchmark version. Open a discussion before adding queries so the version bump and report regeneration are coordinated.
