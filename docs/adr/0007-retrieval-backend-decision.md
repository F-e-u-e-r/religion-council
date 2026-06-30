# ADR 0007 — Retrieval Backend Decision (retrieval-v1 evidence)

- Status: Accepted
- Implementation: **Partially implemented.** Step 1 is shipped as an explicit, opt-in project
  retriever no-answer gate (`retrieve_gated()` / `retrieve_envelope_gated()`) using the t3 lexical
  confidence cutoff. Raw `retrieve()` / `retrieve_envelope()` remain the default surface, so the
  project retriever still ships the v0.12.x file-based lexical ranking by default. The BM25 ranking
  half, any live default flip, and any baseline re-pointing remain deferred to the independent-judge /
  κ gate in §9. No RAG / vector / index / network backend is built here.
- Scope: chooses, from the four measured retrieval-v1 candidates, the **ranking + no-answer policy**
  for the **project** retriever (`orchestrator/project_retrieve.py`). This is a retrieval
  ranking / no-answer policy decision — **not** a RAG / vector / built-index / network-service
  backend selection, and **not** an assurance change.
- Owner stage: the **A2→A3** decision gate ([ADR 0002](0002-roadmap-stage-nomenclature.md) §1;
  [docs/benchmarks/retrieval-v1.md](../benchmarks/retrieval-v1.md), "the gate before a backend is
  chosen"). This ADR resolves the ranking/no-answer half of that gate on corpus tier **C0** and
  records what stays deferred.
- Relationship: consumes the benchmark that [ADR 0006](0006-retriever-fork-contract.md) §6 defers to;
  preserves stable occurrence identity ([ADR 0005](0005-stable-occurrence-identity.md)) and artifact
  lifecycle ([ADR 0003](0003-retrieval-evidence-adapter.md)) as the contracts this decision may not
  weaken.

## Context

`docs/benchmarks/retrieval-v1.md` (v0.12.1) defined the evidence bar before any retrieval backend is
adopted, and ruled that **no index / hybrid / dense / RAG backend is justified until a candidate
beats the lexical baseline on this benchmark _and_ preserves every hard constraint** — and that if
no candidate clears the bar, the file-based lexical retriever stays. Four candidate families have now
been measured against the frozen retrieval-v1 query set (18 queries, 8 categories) and committed
under `docs/benchmarks/results/`:

| family | version | candidate id |
|---|---|---|
| 1. lexical baseline (incumbent) | v0.12.2 | `(baseline)` |
| 2. lexical confidence threshold t2/t3 | v0.12.3 | `lexical-threshold` |
| 3. BM25-style lexical re-ranking | v0.12.4 | `lexical-bm25` (k1=1.2, b=0.75) |
| 4. BM25 + lexical confidence threshold t2/t3 | v0.12.5 | `lexical-bm25-threshold` |

All four are measured **through the ADR 0006 §2 envelope contract** by the same standard-library,
offline, deterministic harness; all carry `retriever_kind: project-file` (no backend was introduced
to measure them — BM25 and the threshold are computed inside the harness as candidate signals). At
the time this ADR was accepted, the C0 corpus was small (56 curated records) and the relevance
judgments were a **single-curator** pass (`independent_judge_count: 1`, IAA `n/a`, disclosed). This
ADR decides which ranking + no-answer policy that evidence supports; it does not enlarge the corpus,
add judges, or build a backend.

## Measured evidence (retrieval-v1, C0, VERSION v0.12.6)

| metric | baseline | threshold t2/t3 | BM25 | **BM25 + t2/t3** |
|---|---|---|---|---|
| Recall@5 | 0.938 | 0.938 | 0.938 | **0.938** |
| nDCG@5 (primary) | 0.902 | 0.902 | 0.919 | **0.919** |
| MRR | 0.938 | 0.938 | 0.969 | **0.969** |
| Exact-span hit rate | 1.000 | 1.000 | 1.000 | **1.000** |
| No-answer correctness | 0.000 | 1.000 | 0.000 | **1.000** |
| False-support rate | 1.000 | 0.000 | 1.000 | **0.000** |
| Citation fidelity | 1.000 | 1.000 | 1.000 | **1.000** |

Reads that matter:

- **BM25 improves ranking modestly and safely:** nDCG@5 +0.0165 (0.902→0.919) and MRR +0.0313
  (0.938→0.969) versus the baseline, while **preserving** the exact-span hit rate (1.000) and recall@5
  (0.938). The k1=1.2 (Lucene default) tuning matters: it earns the ranking gain without the
  exact-locator regression an over-weighted length normalization would cause.
- **The threshold fixes no-answer objectively:** t2 and t3 each take false-support from 1.000 → 0.000
  and no-answer correctness from 0.000 → 1.000, with **zero** answerable-query regression. This is not
  a subjective margin — it is the two off-corpus probes (q014, q015) no longer surfacing noise-floor
  lexical matches. t2 and t3 are **equivalent on retrieval-v1**; t5 (measured in v0.12.3) over-filters
  and regresses q007/q010, so it is excluded.
- **Neither axis fixes broad-thematic recall:** q010 (the cross-tradition "how should one face death"
  query) stays at recall@5 = 0.25 in **every** candidate, including BM25 + t2/t3. The relevant records
  beyond the top hit share little surface vocabulary with the query, which a lexical signal — weighted
  or gated — cannot recover.
- **Every candidate preserves the enforcement-critical contracts:** 100% citation fidelity, the
  corpus-stable occurrence scheme on every retrieved record (`occ/v1-corpus-stable`), `retriever_kind:
  project-file`, `source_assurance` floor `artifact-backed`, and `edition-backed-span-verified: false`.

## Decision

### 1. Select **BM25 + lexical-confidence threshold (t2/t3)** as the project retriever's ranking + no-answer policy

Of the four measured candidates, **BM25 + threshold** is the only one that simultaneously (a) improves
ranking quality (nDCG@5, MRR), (b) eliminates no-answer false support, (c) preserves exact-span lookup
(1.000), and (d) preserves 100% citation fidelity and stable occurrence identity. It is selected as the
ranking + no-answer policy the **project** retriever should adopt — subject to §9 (the one outstanding
gate item) and §8 (scope).

### 2. Why **BM25 alone** is insufficient

BM25 improves ranking but leaves **false-support rate at 1.000** and no-answer correctness at 0.000:
with no confidence gate, the retriever always returns _k_ records, so off-corpus queries (q014, q015)
still surface noise-floor matches as if they were support. A retriever that cannot say "no answer" is
unacceptable for an evidence-bound council where a spurious top hit becomes a citation. BM25 also does
**not** fix the broad-thematic weakness (q010 stays 0.25). So BM25 on its own buys a modest ranking
gain while leaving the most enforcement-relevant weakness — false support — untouched.

### 3. Why the **threshold alone** is insufficient / narrower

The threshold is the right fix for no-answer, but it is **purely a no-answer gate**: it leaves ranking
**identical to the baseline** (nDCG@5 0.902, MRR 0.938 — no change). It does nothing for answerable
queries' ordering and nothing for q010. It is necessary but narrow: it removes false support without
making any correct retrieval better. Adopting only the threshold would lock in the baseline's ranking
when a strictly-better, constraint-preserving ranking (BM25) is available at no measured cost.

### 4. Why **BM25 + threshold** is the best current measured candidate

The two axes are **orthogonal and composable**: BM25 changes the _ordering_ of records that pass the
gate; the threshold decides _whether any record is returned at all_. Composing them inherits both wins
with no measured trade-off — BM25 + t2/t3 matches BM25's ranking (nDCG@5 0.919, MRR 0.969) **and**
the threshold's no-answer behavior (no-answer 1.000, false-support 0.000), while keeping exact-span
hit at 1.000 and citation fidelity at 1.000. No measured metric regresses relative to either component
or to the baseline. Among candidates that clear the hard constraints, this is the one the evidence
prefers.

### 5. What this decision explicitly is **not** (scope guard rails)

This ADR selects a **ranking function + a no-answer policy** over the existing file-based corpus. It is
**not**, and must not be read as:

- **a RAG, vector, dense, hybrid, or built-local-index backend** — none is selected; `retriever_kind`
  stays file-based (no persisted index artifact, no embeddings, no network acquisition);
- **an edition-backed-assurance claim** — beating retrieval-v1 mints **no** span-assurance tier;
  `edition-backed-span-verified` stays tied to A2 edition provenance, not to ranking quality
  ([ADR 0003](0003-retrieval-evidence-adapter.md) §5; retrieval-v1.md hard constraint 6);
- **a change to portable-mode guarantees** — see §6;
- **a solution to broad-thematic recall** — see §7.

### 6. Constraints preserved

- **Portable retriever stays stdlib-only, file-based, and lexical** (retrieval-v1.md hard constraint 4;
  [ADR 0006](0006-retriever-fork-contract.md) §4.4). BM25 + the no-answer gate are adopted in the
  **project** retriever only. Portable and project continue to share the frozen
  `religion-council/retrieval/v1` envelope and the same stable-identity inputs; they may differ in
  ranking _internals_, which ADR 0006 §4.5 explicitly permits. This divergence is a deliberate
  consequence, not a contract change (see Consequences).
- **Stable occurrence identity is preserved.** BM25 only re-orders real corpus records and the gate
  only drops the whole result set; neither mutates record identity. Measured citation fidelity stays
  **1.000** and the only occurrence scheme remains `occ/v1-corpus-stable` (retrieval-v1.md hard
  constraint 2; [ADR 0005](0005-stable-occurrence-identity.md)).
- **Artifact lifecycle is preserved.** Identity remains the content hash of canonical bytes; nothing
  here changes canonicalization or requires hash-on-the-fly from a live file
  ([ADR 0003](0003-retrieval-evidence-adapter.md); retrieval-v1.md hard constraint 3).
- **Determinism is preserved.** The combined candidate is byte-reproducible across processes (the
  benchmark pins this).

### 7. Broad-thematic recall (q010) stays **unresolved**

This decision does **not** solve broad thematic recall. q010 remains recall@5 = 0.25 under every
candidate, because the gap is **vocabulary mismatch**, which no lexical weighting or confidence gate
can close. That weakness should be addressed later, and only on evidence, through one or more of:
**(a) corpus enrichment** (more of the relevant records, with overlapping surface terms / cross-refs);
**(b) benchmark expansion** (more thematic and cross-lingual needs, and the C1 full-text tier when it
exists); **(c) a separate semantic / hybrid experiment** (dense or hybrid retrieval) — which is a
distinct candidate family, gated on its own run against this same bar plus the operational/rights
review, not pre-approved here.

### 8. Implementation scope **if adopted**

When the follow-up implements this decision in `orchestrator/project_retrieve.py`:

1. **Ranking:** replace the project retriever's lexical ordering with the BM25 ranking measured here
   (k1=1.2, b=0.75 — the benchmarked values; any change re-opens the measurement). BM25 corpus
   statistics (document frequency, average length) are computed from the same curated files at load;
   **no persisted index, embedding store, or network call** is introduced. The math is standard-library
   (`math.log`), so adoption adds **no dependency**.
2. **No-answer gate:** apply the t2/t3 cutoff to the **project retriever's lexical confidence score**,
   **not** to BM25's floating-point score — exactly as the `lexical-bm25-threshold` candidate measures
   it (`threshold_score_source: "lexical-baseline"`). BM25 floats are not on the calibrated integer
   scale the t2/t3 cutoffs were tuned against in v0.12.3; the gate must keep using the lexical score's
   known noise floor (1). Pin the exact value at implementation: **t2 and t3 are equivalent on
   retrieval-v1**; t3 is the marginally more conservative no-answer cutoff and is the recommended
   default, with t2 equally supported by the evidence.
3. **Contract & identity:** the change is **internals only** (ADR 0006 §4.5). The envelope contract,
   the required record fields, the stable-identity inputs, and the conformance suite
   (`tests/retrieval_contract/`) are unchanged and must still pass. `retriever_kind` stays file-based
   (it may be refined to a more precise file-based label, but **not** to `project-index` /
   `project-service`, which remain reserved for a real built/served backend under ADR 0006 §6).
4. **Benchmark bookkeeping:** the harness's project↔portable _equivalence_ assumption
   (`test_project_and_portable_are_equivalent`) presumes both retrievers rank identically; once the
   project retriever ranks with BM25, that assumption must be re-pointed (the project retriever is then
   no longer the lexical baseline). The lexical-baseline harness keeps measuring the **portable**
   retriever; the project retriever is measured as the adopted candidate.

### 9. Outstanding gate item before the default ranking flips

retrieval-v1.md **decision gate 2** requires that a candidate beat the baseline on the primary metric
(**nDCG@k on C0**) by a pre-registered, meaningful margin **measured against ≥ 2 independent judges
with a reported inter-annotator agreement (κ)** — precisely because a thin margin over a single
curator's judgments is treated as "not justified." At acceptance time, the evidence was
**single-curator**, and BM25's ranking margin (nDCG@5 +0.0165 on 18 queries) was real but **modest**.
Therefore:

- The **no-answer gate** (the threshold half) is justified **now**: its effect is objective
  (false-support 1.000 → 0.000, zero answerable regression), not a subjective margin, so it does not
  depend on the κ step.
- The **BM25 ranking** half is **selected but gated**: before it flips the project retriever's default
  ranking, the retrieval-v1 judgments must be extended to **≥ 2 independent judges with a κ figure**,
  and the nDCG margin re-confirmed against that set (retrieval-v1.md §Decision gates / §Honest
  limitations). This ADR records the selection and the single open prerequisite; it does not waive it.

Post-v0.13 follow-up note: retrieval-v1 may record disclosed model-judge κ evidence before a human
blind judge exists. That can reduce the single-curator risk if the model limitation is explicit, but
it still does not itself flip BM25 to the default ranking; the project must separately accept whether
that gate evidence is sufficient.

## Consequences

- The project (orchestrated) retriever and the portable (install-free) retriever will **rank
  differently** once this is implemented: project = BM25 + lexical no-answer gate; portable = current
  lexical ranking. They remain identical on the **contract and on evidence identity** (same envelope,
  same `occ/v1-corpus-stable` ids), which is what the enforcement axis depends on; only the _order_ of
  results and the no-answer decision differ. Users of the portable skill keep the simpler, dependency-
  free lexical behavior by design.
- "No backend" remains true in the sense that matters for cost and portability: no index is built or
  stored, no embedding model is chosen, no service is stood up, no new dependency is added, and the
  offline/deterministic guarantees hold.
- The benchmark stays the system of record: this ADR cites specific, reproducible committed runs, and
  any future change to k1/b, the threshold value, or the candidate re-opens a measured comparison
  rather than being decided by intuition.

## Acceptance criteria

- [x] **Compares all four measured candidates** — §"Measured evidence" table + Context table.
- [x] **States why BM25 alone is insufficient** — Decision §2 (false-support stays 1.000).
- [x] **States why the threshold alone is insufficient / narrower** — Decision §3 (ranking unchanged).
- [x] **Explains why BM25 + threshold is the best current measured candidate** — Decision §4
  (orthogonal, composable, no measured regression).
- [x] **Preserves portable retriever constraints** — Decision §6 (portable stays stdlib-only / lexical;
  project-only adoption).
- [x] **Preserves stable occurrence identity** — Decision §6 (citation fidelity 1.000;
  `occ/v1-corpus-stable`; ADR 0005).
- [x] **States no RAG / vector / index backend is selected** — Decision §5; Consequences.
- [x] **States no edition-backed assurance is minted** — Decision §5 (ADR 0003 §5; hard constraint 6).
- [x] **Documents q010 broad-thematic recall as unresolved** — Decision §7.
- [x] **Defines implementation scope if adopted** — Decision §8.

## Non-goals

- Building, choosing, or shipping a **RAG / vector / dense / hybrid / built-local-index / network**
  backend, an embedding model, or a chunking strategy — none is selected; a semantic/hybrid candidate
  is a separate, later, evidence-gated experiment (§7).
- **Changing default retrieval behavior on merge of this ADR** — adoption is a follow-up implementation
  gated on §9; merging this document selects the candidate, it does not flip the retriever.
- **Enlarging the corpus or the judgment set** — corpus enrichment, benchmark expansion, and the ≥2-
  judge + κ extension are named here as prerequisites/follow-ups, not done here.
- **Minting or upgrading any span-assurance tier**, or altering the envelope contract, the identity
  schemes, or the portable retriever — all are fixed inputs to this decision, not its outputs.
