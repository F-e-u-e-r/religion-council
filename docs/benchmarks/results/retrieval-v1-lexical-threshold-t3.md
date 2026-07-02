# Retrieval Benchmark v1 — Candidate: lexical-threshold (threshold=3)

## Status

**Experiment only.** This report evaluates a post-retrieval lexical confidence threshold (top\_score < 3 → no support) against the v0.12.2 lexical baseline. **No default behavior changed.** **No backend selected.**

## Retriever

- retriever_kind: `project-file`
- contract_version: `religion-council/retrieval/v1`
- corpus: C0 curated references — 56 records across 8 traditions (VERSION v0.13.1)
- queries: 18 (16 answerable, 2 no-answer)

## Summary metrics

| metric | @1 | @3 | @5 |
|---|---|---|---|
| Recall | 0.682 | 0.885 | 0.938 |
| Precision | 0.875 | 0.438 | 0.300 |
| nDCG | 0.844 | 0.885 | 0.902 |

- MRR (answerable): **0.938**
- Exact-span hit rate (exact_quote/exact_locator, rank-1 exact target): **1.000**
- No-answer correctness (no spurious lexical match): **1.000**
- False-support rate (no-answer query surfaced a lexical match): **0.000**

## Contract & identity

- Stable occurrence identity present (every retrieved record minted a stable id): **True**
- Occurrence-id schemes: `{'occ/v1-corpus-stable': 37}`
- Required envelope fields present: **True**
- Deterministic repeat (identical ranking on a second pass): **True**
- source_assurance artifact-backed: 37/37 retrieved records
- Curated metadata among retrieved records: representation_kind=11, rights=13
- **Citation fidelity** (returned+relevant records with a reproducible occurrence id across two runs and a reordering): **1.000** (19/19 records)
- Span assurance at retrieval: tier_at_retrieval=`None`, source_assurance floor=`artifact-backed` (37/37 records), edition-backed-span-verified=**False**
- _retrieval mints no span-assurance tier; curated-snapshot-span-verified is minted at B2 and edition-backed-span-verified is reserved for A2 — beating this benchmark upgrades neither (docs/benchmarks/retrieval-v1.md hard constraint 6)._

## Judging provenance

- Independent judges: **2**; inter-annotator agreement: **0.4436** (method: cohen_kappa)
- **Gate evidence — `provisional_model_judge`:** `bm25_default_flip_authorized: false`. A disclosed model-judge κ; flipping BM25 to the default ranking needs explicit owner acceptance or a human blind judge (ADR 0007 §9), not this figure alone.
- ≥2-judge + IAA requirement applies at: backend-selection decision gate (candidate vs. baseline); whether a model-judge kappa suffices or a human blind judge is required is the project owner's call (ADR 0007 §9)
- _retrieval-v1 now carries a second, DISCLOSED MODEL judge (claude-opus-4-8) alongside curator-1. The model judge blind-labeled the frozen pool and Cohen's kappa vs curator-1 is 0.4436 (moderate agreement; raw agreement 76/110). This is PROVISIONAL model-judge evidence — weaker independence than a human blind judge — recorded so the BM25 default-ranking gate (ADR 0007 §9) rests on a disclosed kappa rather than a single-curator margin. It is NOT a human inter-annotator figure and does not by itself authorize flipping the default ranking; the project owner decides whether a model-judge kappa suffices. A future human blind judge can replace or augment the model judge using this same judging.iaa schema. Scoring (judgments[].relevant[]) remains curator-1's authoritative set — the pool affects kappa only, never nDCG/MRR._

## Operational (snapshot — machine-specific, not part of the reproducible metrics)

- records searched per query: 56
- total: 0.0251s · avg query: 1.3954 ms · max query: 2.5706 ms

## Per-query results

| query_id | category | first relevant rank | recall@5 | outcome | top-1 retrieved |
|---|---|---|---|---|---|
| q001 | exact_quote | 1 | 1.000 | hit | 論語·顏淵·reference file entry (score 30) |
| q002 | exact_quote | 1 | 1.000 | hit | 道德經·8 (score 20) |
| q003 | exact_quote | 1 | 1.000 | hit | 般若波羅蜜多心經·reference file entry (score 19) |
| q004 | exact_locator | 1 | 1.000 | hit | 道德經·48 (score 19) |
| q005 | exact_locator | 1 | 1.000 | hit | 約翰福音·3:16 (score 23) |
| q006 | exact_locator | 1 | 1.000 | hit | 古蘭經·1:1(開端章) (score 15) |
| q007 | paraphrased | 2 | 1.000 | hit | 彌迦書·6:8 (score 4) |
| q008 | paraphrased | 1 | 1.000 | hit | 薄伽梵歌·2:47 (score 15) |
| q009 | paraphrased | 1 | 1.000 | hit | 彌迦書·6:8 (score 12) |
| q010 | cross_tradition | 1 | 0.250 | hit | 廣林奧義書·1.3.28 (score 4) |
| q011 | cross_tradition | 1 | 1.000 | hit | 馬太福音·22:37-39 (score 14) |
| q012 | cross_lingual | 1 | 1.000 | hit | 歌者奧義書·6.8.7 (score 16) |
| q013 | cross_lingual | 1 | 1.000 | hit | 布哈里聖訓實錄·開卷傳述(附傳述鏈) (score 6) |
| q014 | no_answer | — | — | no_answer_ok | — |
| q015 | no_answer | — | — | no_answer_ok | — |
| q016 | ambiguous | 2 | 0.750 | hit | 薄伽梵歌·2:47 (score 11) |
| q017 | duplicate_near_duplicate | 1 | 1.000 | hit | 道德經·25 (score 11) |
| q018 | duplicate_near_duplicate | 1 | 1.000 | hit | 法句經·1(南傳) (score 17) |

## Failure analysis

**Missed:** none.

**Partial recall (hit at rank 1 but <50% of relevant records found in top-5):**
- `q010` (cross_tradition): '人應該如何面對死亡' — recall@5 = 0.250; the thematic/relevant records beyond the top hit were not retrieved.

**False support:** none.

## Interpretation

The lexical baseline is strong on exact-quote and exact-locator lookup and on paraphrases that still share surface characters with the source, and it preserves stable occurrence identity and the envelope contract throughout. Its two visible weaknesses are (1) **broad thematic queries** that share little vocabulary with the relevant sources — the cross-tradition death query retrieves only one of four relevant records (recall@5 = 0.25) — and (2) **no-answer discrimination**: having no relevance threshold, the retriever always returns k records, so off-corpus queries surface noise-floor (score 1) false positives. A future local-index / BM25 / hybrid / dense candidate would need to improve thematic recall and add a principled low-confidence cutoff **without** weakening occurrence identity, provenance, or the false-support constraint.

## Non-decision

This result does **not** select a RAG/index/vector backend, does not claim semantic retrieval is better, and does not upgrade any span-assurance tier. Backend selection remains deferred to a future decision ADR that compares candidates against this baseline (docs/benchmarks/retrieval-v1.md §decision gates).

## Comparison vs. v0.12.2 lexical baseline

### Summary metrics

| metric | baseline | threshold=3 | Δ |
|---|---|---|---|
| Recall@1 | 0.682 | 0.682 | — |
| Recall@3 | 0.885 | 0.885 | — |
| Recall@5 | 0.938 | 0.938 | — |
| Precision@1 | 0.875 | 0.875 | — |
| Precision@3 | 0.438 | 0.438 | — |
| Precision@5 | 0.300 | 0.300 | — |
| nDCG@1 | 0.844 | 0.844 | — |
| nDCG@3 | 0.885 | 0.885 | — |
| nDCG@5 | 0.902 | 0.902 | — |
| MRR | 0.938 | 0.938 | — |
| Exact-span hit | 1.000 | 1.000 | — |
| No-answer correct | 0.000 | 1.000 | +1.000 |
| False-support | 1.000 | 0.000 | -1.000 |

### Per-query changes

**Improved:**
- `q014` (no_answer): false_support → no_answer_ok (top score 1)
- `q015` (no_answer): false_support → no_answer_ok (top score 1)

**Regressed:** none.

**Unchanged:** 16 queries.
