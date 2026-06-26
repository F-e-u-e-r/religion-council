# Retrieval Benchmark v1 — Candidate: lexical-threshold (threshold=5)

## Status

**Experiment only.** This report evaluates a post-retrieval lexical confidence threshold (top\_score < 5 → no support) against the v0.12.2 lexical baseline. **No default behavior changed.** **No backend selected.**

## Retriever

- retriever_kind: `project-file`
- contract_version: `religion-council/retrieval/v1`
- corpus: C0 curated references — 56 records across 8 traditions (VERSION v0.12.6)
- queries: 18 (16 answerable, 2 no-answer)

## Summary metrics

| metric | @1 | @3 | @5 |
|---|---|---|---|
| Recall | 0.667 | 0.807 | 0.859 |
| Precision | 0.812 | 0.396 | 0.275 |
| nDCG | 0.812 | 0.829 | 0.848 |

- MRR (answerable): **0.844**
- Exact-span hit rate (exact_quote/exact_locator, rank-1 exact target): **1.000**
- No-answer correctness (no spurious lexical match): **1.000**
- False-support rate (no-answer query surfaced a lexical match): **0.000**

## Contract & identity

- Stable occurrence identity present (every retrieved record minted a stable id): **True**
- Occurrence-id schemes: `{'occ/v1-corpus-stable': 36}`
- Required envelope fields present: **True**
- Deterministic repeat (identical ranking on a second pass): **True**
- source_assurance artifact-backed: 36/36 retrieved records
- Curated metadata among retrieved records: representation_kind=6, rights=10
- **Citation fidelity** (returned+relevant records with a reproducible occurrence id across two runs and a reordering): **1.000** (18/18 records)
- Span assurance at retrieval: tier_at_retrieval=`None`, source_assurance floor=`artifact-backed` (36/36 records), edition-backed-span-verified=**False**
- _retrieval mints no span-assurance tier; curated-snapshot-span-verified is minted at B2 and edition-backed-span-verified is reserved for A2 — beating this benchmark upgrades neither (docs/benchmarks/retrieval-v1.md hard constraint 6)._

## Judging provenance

- Independent judges: **1**; inter-annotator agreement: **n/a** (method: cohen_kappa)
- ≥2-judge + IAA requirement applies at: backend-selection decision gate (candidate vs. baseline), deferred to ADR 0007
- _retrieval-v1 baseline judgments are a single-curator pass; no second independent judge exists for the baseline, so no inter-annotator-agreement figure is available (reported as n/a, not fabricated). Per docs/benchmarks/retrieval-v1.md, >=2 independent judges and an IAA figure are required when a candidate backend is compared against this baseline at the decision gate, not to establish the baseline measurement itself. The labels here are deliberately objective (exact quotes, locators, and source-grounded paraphrase/theme calls each carry a rationale) to bound that subjectivity for the baseline._

## Operational (snapshot — machine-specific, not part of the reproducible metrics)

- records searched per query: 56
- total: 0.0214s · avg query: 1.1865 ms · max query: 1.7971 ms

## Per-query results

| query_id | category | first relevant rank | recall@5 | outcome | top-1 retrieved |
|---|---|---|---|---|---|
| q001 | exact_quote | 1 | 1.000 | hit | 論語·顏淵·reference file entry (score 30) |
| q002 | exact_quote | 1 | 1.000 | hit | 道德經·8 (score 20) |
| q003 | exact_quote | 1 | 1.000 | hit | 般若波羅蜜多心經·reference file entry (score 19) |
| q004 | exact_locator | 1 | 1.000 | hit | 道德經·48 (score 19) |
| q005 | exact_locator | 1 | 1.000 | hit | 約翰福音·3:16 (score 23) |
| q006 | exact_locator | 1 | 1.000 | hit | 古蘭經·1:1(開端章) (score 15) |
| q007 | paraphrased | — | 0.000 | miss | — |
| q008 | paraphrased | 1 | 1.000 | hit | 薄伽梵歌·2:47 (score 15) |
| q009 | paraphrased | 1 | 1.000 | hit | 彌迦書·6:8 (score 12) |
| q010 | cross_tradition | — | 0.000 | miss | — |
| q011 | cross_tradition | 1 | 1.000 | hit | 馬太福音·22:37-39 (score 14) |
| q012 | cross_lingual | 1 | 1.000 | hit | 歌者奧義書·6.8.7 (score 16) |
| q013 | cross_lingual | 1 | 1.000 | hit | 布哈里聖訓實錄·開卷傳述(附傳述鏈) (score 6) |
| q014 | no_answer | — | — | no_answer_ok | — |
| q015 | no_answer | — | — | no_answer_ok | — |
| q016 | ambiguous | 2 | 0.750 | hit | 薄伽梵歌·2:47 (score 11) |
| q017 | duplicate_near_duplicate | 1 | 1.000 | hit | 道德經·25 (score 11) |
| q018 | duplicate_near_duplicate | 1 | 1.000 | hit | 法句經·1(南傳) (score 17) |

## Failure analysis

**Missed (no relevant record in top-5):**
- `q007` (paraphrased): '不要把自己不想要的事強加給別人' — relevant material exists but was not retrieved.
- `q010` (cross_tradition): '人應該如何面對死亡' — relevant material exists but was not retrieved.

**False support:** none.

## Interpretation

The lexical baseline is strong on exact-quote and exact-locator lookup and on paraphrases that still share surface characters with the source, and it preserves stable occurrence identity and the envelope contract throughout. Its two visible weaknesses are (1) **broad thematic queries** that share little vocabulary with the relevant sources — the cross-tradition death query retrieves only one of four relevant records (recall@5 = 0.25) — and (2) **no-answer discrimination**: having no relevance threshold, the retriever always returns k records, so off-corpus queries surface noise-floor (score 1) false positives. A future local-index / BM25 / hybrid / dense candidate would need to improve thematic recall and add a principled low-confidence cutoff **without** weakening occurrence identity, provenance, or the false-support constraint.

## Non-decision

This result does **not** select a RAG/index/vector backend, does not claim semantic retrieval is better, and does not upgrade any span-assurance tier. Backend selection remains deferred to a future decision ADR that compares candidates against this baseline (docs/benchmarks/retrieval-v1.md §decision gates).

## Comparison vs. v0.12.2 lexical baseline

### Summary metrics

| metric | baseline | threshold=5 | Δ |
|---|---|---|---|
| Recall@1 | 0.682 | 0.667 | -0.016 |
| Recall@3 | 0.885 | 0.807 | -0.078 |
| Recall@5 | 0.938 | 0.859 | -0.078 |
| Precision@1 | 0.875 | 0.812 | -0.062 |
| Precision@3 | 0.438 | 0.396 | -0.042 |
| Precision@5 | 0.300 | 0.275 | -0.025 |
| nDCG@1 | 0.844 | 0.812 | -0.031 |
| nDCG@3 | 0.885 | 0.829 | -0.056 |
| nDCG@5 | 0.902 | 0.848 | -0.054 |
| MRR | 0.938 | 0.844 | -0.094 |
| Exact-span hit | 1.000 | 1.000 | — |
| No-answer correct | 0.000 | 1.000 | +1.000 |
| False-support | 1.000 | 0.000 | -1.000 |

### Per-query changes

**Improved:**
- `q014` (no_answer): false_support → no_answer_ok (top score 1)
- `q015` (no_answer): false_support → no_answer_ok (top score 1)

**Regressed:**
- `q007` (paraphrased): hit → miss (top score 4)
- `q010` (cross_tradition): hit → miss (top score 4)

**Unchanged:** 14 queries.
