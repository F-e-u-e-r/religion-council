# Retrieval Benchmark v1 — the gate before a backend is chosen

- Status:
  - Benchmark definition: **complete** (v0.12.1).
  - Lexical baseline execution: **complete** (v0.12.2). The first run — the file-based lexical
    baseline — is committed at
    [results/retrieval-v1-lexical-baseline.md](results/retrieval-v1-lexical-baseline.md) (runner:
    `scripts/run_retrieval_benchmark.py`; frozen query set + judgments under `queries/` and
    `judgments/`).
  - Lexical confidence threshold experiment: **complete** (v0.12.3). Thresholds 1, 2, 3, and 5 are
    committed under `results/`; thresholds 2 and 3 eliminate the two no-answer false-support cases
    without answerable-query regression, while threshold 5 regresses q007 and q010. This remains an
    experiment only: no default threshold and no backend is adopted.
  - BM25-style lexical re-ranking experiment: **complete** (v0.12.4). A BM25 re-ranking of the
    same file corpus over the same tokenization (Lucene-style defaults: k1=1.2, b=0.75) is committed
    under `results/` ([retrieval-v1-lexical-bm25.md](results/retrieval-v1-lexical-bm25.md)). On C0 it
    improves some ranking metrics (MRR 0.938 → 0.969, nDCG@5 0.902 → 0.919) and preserves exact-span
    hit rate (1.000), but it does not fix the broad-thematic weakness (q010 stays recall@5 = 0.25)
    or no-answer discrimination (false-support stays 1.0; threshold t2/t3 remain better for
    no-answer). This is candidate family 2 and remains an experiment only: no backend is adopted.
    The result is consistent with "Why this gate exists" — on a small, multilingual,
    classical-Chinese corpus, exact-term/locator matching already does much of the work and a ranker
    alone is not a no-answer policy.
  - BM25 + lexical confidence threshold experiment: **complete** (v0.12.5). The combined
    candidate is committed under `results/`
    ([t2](results/retrieval-v1-lexical-bm25-threshold-t2.md),
    [t3](results/retrieval-v1-lexical-bm25-threshold-t3.md)). BM25 supplies the ranking signal while
    the v0.12.3 lexical confidence gate supplies no-answer discrimination. On C0, BM25+t2/t3 preserve
    the BM25 ranking improvements (MRR 0.969, nDCG@5 0.919) and exact-span hit rate (1.000), while
    eliminating no-answer false-support (no-answer correctness 1.000, false-support 0.000). The
    broad-thematic weakness remains: q010 stays recall@5 = 0.25. This is still measurement only:
    no threshold, ranker, backend, vector store, or RAG path is adopted.
  - Ranking + no-answer decision: **accepted** (v0.12.6;
    [ADR 0007](../adr/0007-retrieval-backend-decision.md)).
    From the four reference runs — lexical baseline, confidence threshold, BM25, and BM25+threshold —
    ADR 0007 selects **BM25 + lexical-confidence threshold (t2/t3)** as the project retriever's ranking
    + no-answer policy, scoped as an internals change (ADR 0006 §4.5), with the default-ranking flip
    gated on the ≥2-judge + κ step (decision gate 2). Broad-thematic recall (q010) is recorded as
    unresolved.
  - Backend selection: **deferred.** No RAG / vector / dense / hybrid / built-local-index / network
    backend is measured or selected by this document or by ADR 0007 — that remains gated on a separate,
    evidence-justified experiment plus the operational/rights review.
- Owner stage: the **A2→A3** decision gate ([ADR 0002](../adr/0002-roadmap-stage-nomenclature.md) §1):
  whether to move retrieval beyond today's file-based lexical ranking to a local index, a hybrid, or
  a dense/vector backend — and, separately, to a networked RAG service.
- Relationship: this is the benchmark [ADR 0006](../adr/0006-retriever-fork-contract.md) §6 and its
  migration phase 5 defer to. ADR 0006 fixed the **contract** (one retrieval envelope, two
  retrievers, stable identity minted downstream); this document fixes the **evidence bar** a backend
  must clear before the project retriever may adopt it. The two are deliberately separate: the
  contract must exist before the benchmark, and the benchmark must exist before a backend.

## Why this gate exists

The roadmap has always said retrieval *may* grow from file-based lexical ranking to a local index or
a vector store "without touching the personas." That freedom is real only if the project refuses to
adopt a heavier backend on intuition. Dense retrieval is not automatically better than lexical
retrieval — especially on a small, multilingual, classical-Chinese corpus where exact-term and
locator matching already do most of the work — and it is strictly more expensive, more dependency-
heavy, and harder to make reproducible. Adopting it without measured justification would trade the
project's portability and determinism for an unproven quality gain.

So: **no local index, hybrid ranker, dense/vector backend, or RAG service is justified until a
candidate beats the lexical baseline on this benchmark *and* preserves every hard constraint below.**
If no candidate clears the bar, the file-based lexical retriever stays — that is an acceptable,
expected outcome, not a failure of the benchmark.

## What the benchmark must decide

For the **project** retriever (`orchestrator/project_retrieve.py`), rank these candidate families and
decide which, if any, is justified:

1. **Lexical baseline** — today's deterministic file parse + lexical scoring (the incumbent; the bar).
2. **Local lexical index** — the same lexical signal behind a built index (e.g. an inverted index /
   BM25-style ranker) for scale, still offline and in-repo.
3. **Hybrid** — lexical signal fused with a dense signal.
4. **Dense / vector** — embedding-based semantic retrieval.

A separate, later question — putting the chosen index *behind a network service* (A3) — is **out of
scope here**; it is gated on this benchmark plus an operational/rights review, not decided by it.

## Hard constraints (a candidate that violates any is disqualified regardless of score)

Retrieval quality is **necessary but not sufficient.** A candidate must also preserve the contracts
the enforcement axis depends on:

1. **Envelope contract ([ADR 0006](../adr/0006-retriever-fork-contract.md)).** Output the same
   `religion-council/retrieval/v1` envelope and required record fields. A backend change is an
   internals change, never a contract change. Must pass `tests/retrieval_contract/`.
2. **Stable occurrence identity ([ADR 0005](../adr/0005-stable-occurrence-identity.md)).** A reorderable
   or dynamically-acquired backend must still supply stable-identity inputs (`record_key`, or
   `work`+`locator`, or `source_file`+`source_line`) so the adapter mints an order-independent
   occurrence id — or it must fail closed. A candidate whose ranking makes evidence identity
   order-dependent is disqualified. This is measured directly (the citation-fidelity metric below),
   not assumed.
3. **Artifact lifecycle ([ADR 0003](../adr/0003-retrieval-evidence-adapter.md)).** Identity is the
   content hash of canonical bytes (`UTF-8(NFC(LF(text)))`); a candidate must not require a different
   canonicalization or hash-on-the-fly from a live file.
4. **Portable retriever stays stdlib-only and lexical.** Any index/embedding/vector dependency lives
   in the **project** retriever only. The portable `skills/` retriever does **not** adopt a backend
   from this benchmark; it remains install-free, file-based, and lexical (ADR 0006 §4.4). A "win"
   that can only be delivered by adding a dependency to the portable retriever is not adoptable.
5. **Rights gate.** Any candidate that requires storing **full text** beyond the curated excerpts
   triggers the A2 operational rights review (`docs/CORPUS.md` → Rights gate): rights basis,
   jurisdiction notes, `redistributable = true`, and a review date before material enters the
   distributable corpus. The benchmark may run over a restricted/private store, but adoption cannot
   ship un-cleared text.
6. **No edition-backed-assurance claim.** Beating the benchmark does not upgrade the span-assurance
   tier. `edition-backed-span-verified` remains tied to edition provenance (A2 corpus work), not to
   retrieval quality.
7. **Determinism where required.** For a fixed `(corpus, query, k)` the candidate must return a
   deterministic result (ADR 0006 §4.6); a nondeterministic ranker must be pinned (fixed seed /
   tie-break) before it is benchmarkable.

## Evaluation design

### Corpus under test

Two tiers, reported separately:

- **Tier C0 — curated references (available now).** The records the portable retriever returns over
  `references/` (the same set `scripts/corpus_inventory.py` inventories). Small (tens of records),
  multilingual (`zh-Hant`, `lzh`, plus renderings), with real locators. This is what exists today and
  is fully reproducible.
- **Tier C1 — full-text corpus (A2, when it exists).** The chunked open scriptures of A2. The
  benchmark is *defined* for C1 but cannot be *run* on it until that corpus + its rights clearance
  exist. C1 results, when available, do not retroactively change a C0 decision; they are a separate
  gate for the larger corpus.

### Query set

A versioned, in-repo set of information needs, each tagged with tradition(s) and need-type
(definitional / cross-tradition-contrast / locator-lookup / thematic). It must include:

- single-tradition needs that the lexical baseline already serves (guarding against regressions);
- cross-lingual needs (a query in modern Chinese against a classical-Chinese or rendered source),
  the case dense retrieval is most likely to help;
- paraphrase/synonymy needs (the query shares meaning but not surface terms with the source);
- needs with **no good answer in the corpus** (to measure false-positive / over-retrieval behavior).

The query set is data, not code, and is frozen per benchmark version (`retrieval-v1`); changing it
mints `retrieval-v2`.

### Relevance judgments

Graded relevance (e.g. 0/1/2) per `(query, record)` pair, with:

- judgments recorded in-repo alongside the query set, with a short rationale per positive label;
- a disclosed **judging provenance** block (`judgments/retrieval-v1.json` → `judging`, surfaced in
  every report): judge identities, the independent-judge count, the inter-annotator-agreement figure
  (or an explicit `n/a`), and the agreement method. The benchmark must *disclose* how subjective the
  judgments are; it must not silently omit provenance;
- **≥ 2 judges** on a sampled subset with an inter-annotator-agreement figure (Cohen's κ) reported
  **when a candidate backend is compared against the baseline at the decision gate** — that is the
  point where a subjective margin decides adoption, so the disagreement among judges must be
  quantified there. The original baseline measurement was a single-curator pass (`κ: n/a`, disclosed,
  never fabricated); the additive `judging.iaa` pool below is the mechanism for adding second-judge
  labels without changing the authoritative scoring set. Adding the second judge + κ is a
  prerequisite of the deferred backend-selection ADR, not of establishing the lexical baseline;
- judgments keyed to **stable occurrence identity**, not list position, so they survive reordering
  and backend changes.

**Computing κ.** The agreement figure is computed by
`scripts/compute_iaa.py` (standard-library, offline, deterministic) from an additive, optional
`judging.iaa` block — a fixed *pool* of `(query, record)` items that every judge grades, including the
records a judge calls *not* relevant (so disagreement is observable). The scoring set
`judgments[].relevant[]` lists only positives and is left untouched:

```json
"judging": {
  "iaa": {
    "label_set": [0, 1, 2],
    "pool": [
      {"query_id": "q001", "tradition": "…", "work": "…", "locator": "…",
       "labels": {"curator-1": 2, "judge-2": 1}}
    ]
  }
}
```

With fewer than two judges in the pool, the tool and every benchmark report show `κ: n/a` (a
single-curator state — disclosed, never fabricated). When a second judge's labels are added, Cohen's κ
is computed and surfaced automatically (`python3 scripts/compute_iaa.py`).

**Provisional second judge (disclosed model judge).** A disclosed model judge (`claude-opus-4-8`) has
blind-labeled the 110-item pool (query + record content, objective rubric; blind to curator-1's labels
and to candidate scores). Cohen's κ vs curator-1 is **0.4436** (moderate; raw agreement 76/110).
Re-scoring nDCG@5 under the model judge's labels, BM25 and BM25+t3 still beat the lexical baseline
(**0.898 → 0.932**, vs **0.902 → 0.919** under curator-1), so BM25's ranking advantage is
directionally robust to this second judge — though the margin stays thin and κ only moderate. This is
**provisional model-judge evidence**: it is disclosed as a model (not human) judge and does **not**
authorize flipping the default ranking; a human blind judge may replace or augment it via the same
schema (ADR 0007 §9).

### Metrics

Reported per candidate, per corpus tier, with the lexical baseline as the reference column:

- **Retrieval quality:** Recall@k and nDCG@k for the operating `k` (and a small sweep), plus MRR for
  locator-lookup needs.
- **Citation fidelity (the enforcement-critical metric):** the fraction of returned, relevant records
  that yield a **stable, reproducible occurrence id** across two runs and across a reordering of the
  result list. A candidate below 100% here is disqualified by constraint 2 above — this metric exists
  to make that failure visible and quantified, not negotiable.
- **Operational cost:** index build time + size, query latency (p50/p95), dependency footprint, and
  whether the candidate is offline. These are first-class: a marginal quality win that triples
  latency or adds a heavy dependency is not automatically justified.

### Protocol

- A reproducible harness — `scripts/run_retrieval_benchmark.py`, standard-library only, offline,
  deterministic — over the frozen query set (`queries/retrieval-v1.json`) + judgments
  (`judgments/retrieval-v1.json`) emits a single report; rerunning it on the same inputs reproduces
  the JSON byte-for-byte (wall-clock timing is reported only in the Markdown snapshot, never in the
  reproducible JSON, and occurrence-id hashes — which embed an absolute path under ADR 0005 — are
  deliberately excluded so the report is checkout-portable).
- The harness measures through the **contract**, not internals: it acquires candidates via the
  retriever's per-tradition `retrieve_envelope()` (ADR 0006 §2) and feeds those real envelopes —
  carrying the retriever's own `contract_version` — through the **real** B1 adapter, so the
  identity/contract metrics measure what the contract emits, not a hand-built parse. It confirms a
  stable `occ/v1-corpus-stable` occurrence id is minted (the actual identity the enforcement axis
  would use, not a proxy), and reports a concrete span-assurance status (no tier is minted at
  retrieval; the artifact-backed `source_assurance` floor is). It is the **lexical-baseline** harness
  and refuses any non-`*-file` `retriever_kind`, so a future index/hybrid/dense/service backend is
  measured by the backend-selection harness, never silently mismeasured here.
- **Citation fidelity is measured, not assumed:** the harness mints the occurrence id of every
  returned+relevant record across two independent adapter runs **and** a reordering of the result
  list, and reports the fraction that agree (1.0 for the corpus-stable scheme; a backend that made
  identity order-dependent would score below 1.0 and be disqualified by hard constraint 2).
- Each report carries the **judging provenance** (`judging` block): judge count, IAA (or `n/a`), and
  the disclosure scoping the ≥2-judge requirement to the decision gate.
- Results are committed under `results/`
  ([lexical baseline](results/retrieval-v1-lexical-baseline.md)) so a future backend-selection ADR
  can cite a specific, reproducible run; `tests/test_retrieval_benchmark.py` fails if the committed
  baseline drifts from the runner, and CI validates the fixtures (`--check-fixtures`).

## Decision gates

A candidate is **justified for adoption by the project retriever** only if **all** hold:

1. it passes every hard constraint (above) — including 100% citation fidelity and the contract suite;
2. it beats the lexical baseline by a pre-registered, meaningful margin on the **primary** metric
   (nDCG@k on C0), measured against a judgment set extended to **≥ 2 independent judges with a
   reported inter-annotator agreement** (κ), not merely within noise or within one curator's
   subjectivity;
3. its operational cost is within a stated budget (offline; no portable-retriever dependency; latency
   and footprint acceptable for the orchestrated council);
4. if it needs full text, the C1 rights review has cleared the material it depends on.

If two candidates both clear the bar, prefer the **simpler / cheaper / more portable** one (a local
lexical index over a dense backend, a dense backend over a networked service), because the project's
default is the least machinery that meets the need.

If **no** candidate clears the bar on C0, the file-based lexical retriever remains the project
retriever, and this document records that outcome with the run that produced it.

## Non-goals

- **Running the benchmark** or publishing results — this document defines it; a dated report and a
  backend-selection ADR come later.
- **Choosing an embedding model, a vector database, a chunking strategy, or a ranking algorithm** —
  those are candidate-configuration details decided by the run, not pre-judged here.
- **Designing the A3 network retrieval service or any API** — that is a separate, later gate.
- **Changing the retrieval envelope contract, the identity schemes, or the portable retriever** — all
  three are fixed inputs to the benchmark, not its outputs.

## Honest limitations

- C0 is small; absolute metric values are noisy, so the gate is a **margin over the baseline**, not an
  absolute threshold, and the primary decision is reported with its uncertainty.
- Relevance is subjective. The original baseline measurement was **single-curator**; the current
  fixture adds a disclosed model-judge κ pool as provisional evidence, not a human IAA claim and not
  an automatic BM25 default flip. A thin margin over an uncertain judgment set is treated as
  "not justified," not "justified," until the project explicitly accepts the gate evidence.
- Offline retrieval metrics are a proxy for debate quality, not debate quality itself; a backend that
  wins the benchmark still ships behind the same B-axis enforcement and the same assurance honesty.
