# Retrieval Benchmark v1 — Candidate: lexical-bm25-threshold (threshold=2, k1=1.2, b=0.75)

## Status

**Experiment only.** This report combines BM25-style lexical re-ranking (k1=1.2, b=0.75) with the lexical confidence threshold from the v0.12.3 experiment (baseline lexical top\_score < 2 → no support). BM25 ranks the records that pass the lexical confidence gate; the threshold is not applied to BM25's floating-point score scale. The project/portable retrievers are unchanged; BM25 and thresholding are computed only in the benchmark harness. **No default behavior changed.** **No backend selected.**

## Retriever

- retriever_kind: `project-file`
- contract_version: `religion-council/retrieval/v1`
- corpus: C0 curated references — 56 records across 8 traditions (VERSION v0.12.5)
- queries: 18 (16 answerable, 2 no-answer)

## Summary metrics

| metric | @1 | @3 | @5 |
|---|---|---|---|
| Recall | 0.698 | 0.901 | 0.938 |
| Precision | 0.938 | 0.458 | 0.300 |
| nDCG | 0.906 | 0.913 | 0.919 |

- MRR (answerable): **0.969**
- Exact-span hit rate (exact_quote/exact_locator, rank-1 exact target): **1.000**
- No-answer correctness (no spurious lexical match): **1.000**
- False-support rate (no-answer query surfaced a lexical match): **0.000**

## Contract & identity

- Stable occurrence identity present (every retrieved record minted a stable id): **True**
- Occurrence-id schemes: `{'occ/v1-corpus-stable': 38}`
- Required envelope fields present: **True**
- Deterministic repeat (identical ranking on a second pass): **True**
- source_assurance artifact-backed: 38/38 retrieved records
- Curated metadata among retrieved records: representation_kind=7, rights=13
- **Citation fidelity** (returned+relevant records with a reproducible occurrence id across two runs and a reordering): **1.000** (19/19 records)
- Span assurance at retrieval: tier_at_retrieval=`None`, source_assurance floor=`artifact-backed` (38/38 records), edition-backed-span-verified=**False**
- _retrieval mints no span-assurance tier; curated-snapshot-span-verified is minted at B2 and edition-backed-span-verified is reserved for A2 — beating this benchmark upgrades neither (docs/benchmarks/retrieval-v1.md hard constraint 6)._

## Judging provenance

- Independent judges: **1**; inter-annotator agreement: **n/a** (method: cohen_kappa)
- ≥2-judge + IAA requirement applies at: backend-selection decision gate (candidate vs. baseline), deferred to ADR 0007
- _retrieval-v1 baseline judgments are a single-curator pass; no second independent judge exists for the baseline, so no inter-annotator-agreement figure is available (reported as n/a, not fabricated). Per docs/benchmarks/retrieval-v1.md, >=2 independent judges and an IAA figure are required when a candidate backend is compared against this baseline at the decision gate, not to establish the baseline measurement itself. The labels here are deliberately objective (exact quotes, locators, and source-grounded paraphrase/theme calls each carry a rationale) to bound that subjectivity for the baseline._

## Operational (snapshot — machine-specific, not part of the reproducible metrics)

- records searched per query: 56
- total: 0.0371s · avg query: 2.0638 ms · max query: 3.0428 ms

## Per-query results

| query_id | category | first relevant rank | recall@5 | outcome | top-1 retrieved |
|---|---|---|---|---|---|
| q001 | exact_quote | 1 | 1.000 | hit | 論語·顏淵·reference file entry (score 48.992896) |
| q002 | exact_quote | 1 | 1.000 | hit | 道德經·8 (score 32.216944) |
| q003 | exact_quote | 1 | 1.000 | hit | 般若波羅蜜多心經·reference file entry (score 25.727914) |
| q004 | exact_locator | 1 | 1.000 | hit | 道德經·48 (score 38.456529) |
| q005 | exact_locator | 1 | 1.000 | hit | 約翰福音·3:16 (score 21.572816) |
| q006 | exact_locator | 1 | 1.000 | hit | 古蘭經·1:1(開端章) (score 29.912382) |
| q007 | paraphrased | 2 | 1.000 | hit | 馬太福音·22:37-39 (score 7.849678) |
| q008 | paraphrased | 1 | 1.000 | hit | 薄伽梵歌·2:47 (score 31.790297) |
| q009 | paraphrased | 1 | 1.000 | hit | 彌迦書·6:8 (score 19.693994) |
| q010 | cross_tradition | 1 | 0.250 | hit | 廣林奧義書·1.3.28 (score 8.412802) |
| q011 | cross_tradition | 1 | 1.000 | hit | 馬太福音·22:37-39 (score 8.321731) |
| q012 | cross_lingual | 1 | 1.000 | hit | 歌者奧義書·6.8.7 (score 12.321807) |
| q013 | cross_lingual | 1 | 1.000 | hit | 布哈里聖訓實錄·開卷傳述(附傳述鏈) (score 13.753182) |
| q014 | no_answer | — | — | no_answer_ok | — |
| q015 | no_answer | — | — | no_answer_ok | — |
| q016 | ambiguous | 1 | 0.750 | hit | 道德經·1 (score 2.366786) |
| q017 | duplicate_near_duplicate | 1 | 1.000 | hit | 道德經·25 (score 25.663114) |
| q018 | duplicate_near_duplicate | 1 | 1.000 | hit | 法句經·1(南傳) (score 13.41893) |

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

| metric | baseline | bm25+t2 (k1=1.2, b=0.75) | Δ |
|---|---|---|---|
| Recall@1 | 0.682 | 0.698 | +0.016 |
| Recall@3 | 0.885 | 0.901 | +0.016 |
| Recall@5 | 0.938 | 0.938 | — |
| Precision@1 | 0.875 | 0.938 | +0.062 |
| Precision@3 | 0.438 | 0.458 | +0.021 |
| Precision@5 | 0.300 | 0.300 | — |
| nDCG@1 | 0.844 | 0.906 | +0.062 |
| nDCG@3 | 0.885 | 0.913 | +0.027 |
| nDCG@5 | 0.902 | 0.919 | +0.016 |
| MRR | 0.938 | 0.969 | +0.031 |
| Exact-span hit | 1.000 | 1.000 | — |
| No-answer correct | 0.000 | 1.000 | +1.000 |
| False-support | 1.000 | 0.000 | -1.000 |

### Per-query changes (first-relevant rank · recall@5; no-answer outcome)

**Improved:**
- `q014` (no_answer): false_support → no_answer_ok (pre-threshold top score 1)
- `q015` (no_answer): false_support → no_answer_ok (pre-threshold top score 1)
- `q016` (ambiguous): rank 2 → 1, recall@5 0.750 → 0.750

**Regressed:** none.

**Unchanged:** 15 queries.

## Comparison across retrieval-v1 reference candidates

This table compares the current combined candidate against the committed lexical baseline, threshold t2/t3, and BM25-only reports. These are measurements only: no backend or threshold behavior is adopted here.

### Summary metrics

| metric | baseline | threshold t2 | threshold t3 | BM25 | BM25+t2 | BM25+t3 |
|---|---|---|---|---|---|---|
| Recall@1 | 0.682 | 0.682 | 0.682 | 0.698 | 0.698 | 0.698 |
| Recall@3 | 0.885 | 0.885 | 0.885 | 0.901 | 0.901 | 0.901 |
| Recall@5 | 0.938 | 0.938 | 0.938 | 0.938 | 0.938 | 0.938 |
| Precision@1 | 0.875 | 0.875 | 0.875 | 0.938 | 0.938 | 0.938 |
| Precision@3 | 0.438 | 0.438 | 0.438 | 0.458 | 0.458 | 0.458 |
| Precision@5 | 0.300 | 0.300 | 0.300 | 0.300 | 0.300 | 0.300 |
| nDCG@1 | 0.844 | 0.844 | 0.844 | 0.906 | 0.906 | 0.906 |
| nDCG@3 | 0.885 | 0.885 | 0.885 | 0.913 | 0.913 | 0.913 |
| nDCG@5 | 0.902 | 0.902 | 0.902 | 0.919 | 0.919 | 0.919 |
| MRR | 0.938 | 0.938 | 0.938 | 0.969 | 0.969 | 0.969 |
| Exact-span hit | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| No-answer correct | 0.000 | 1.000 | 1.000 | 0.000 | 1.000 | 1.000 |
| False-support | 1.000 | 0.000 | 0.000 | 1.000 | 0.000 | 0.000 |

### Targeted query comparison

| focus | baseline | threshold t2 | threshold t3 | BM25 | BM25+t2 | BM25+t3 |
|---|---|---|---|---|---|---|
| exact locator: John 3:16 (`q005`) | hit; rank 1; recall@5 1.000 | hit; rank 1; recall@5 1.000 | hit; rank 1; recall@5 1.000 | hit; rank 1; recall@5 1.000 | hit; rank 1; recall@5 1.000 | hit; rank 1; recall@5 1.000 |
| paraphrase: do not impose on others (`q007`) | hit; rank 2; recall@5 1.000 | hit; rank 2; recall@5 1.000 | hit; rank 2; recall@5 1.000 | hit; rank 2; recall@5 1.000 | hit; rank 2; recall@5 1.000 | hit; rank 2; recall@5 1.000 |
| broad cross-tradition: facing death (`q010`) | hit; rank 1; recall@5 0.250 | hit; rank 1; recall@5 0.250 | hit; rank 1; recall@5 0.250 | hit; rank 1; recall@5 0.250 | hit; rank 1; recall@5 0.250 | hit; rank 1; recall@5 0.250 |
| no-answer: crypto investment (`q014`) | false_support; top-1 布哈里聖訓實錄·開卷傳述(附傳述鏈) (score 1) | no_answer_ok; top-1 — | no_answer_ok; top-1 — | false_support; top-1 布哈里聖訓實錄·開卷傳述(附傳述鏈) (score 3.177883) | no_answer_ok; top-1 — | no_answer_ok; top-1 — |
| no-answer: smartphone specs (`q015`) | false_support; top-1 薄伽梵歌·2:20 (score 1) | no_answer_ok; top-1 — | no_answer_ok; top-1 — | false_support; top-1 廣林奧義書·1.4.10 (score 4.066262) | no_answer_ok; top-1 — | no_answer_ok; top-1 — |

### Takeaway

- BM25+threshold preserves the BM25 exact-span behavior and applies the threshold no-answer cutoff.
- `q010` remains the broad-thematic weak point; lexical ranking plus thresholding does not increase its recall@5 above 0.250 on retrieval-v1.
- No backend is selected; ADR 0007 remains deferred until these candidates are compared as a decision, not merely measured.
