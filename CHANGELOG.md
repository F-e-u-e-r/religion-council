# Changelog

All notable changes to this project are documented here. Entries are grouped by release tag and
framed around the project's two architecture axes (see
[ADR 0002](docs/adr/0002-roadmap-stage-nomenclature.md)):

- **Axis A — corpus & retrieval:** `A0`–`A3`
- **Axis B — admissibility & enforcement:** `B0`–`B3`

The format is adapted from [Keep a Changelog](https://keepachangelog.com/); versions follow
`vMAJOR.MINOR.PATCH`. (The first tag `v0.1` predates that convention and is kept as-is.)

## [Unreleased]

### Changed
- Deferred follow-up: rename the older controller `renderer-bypass` boundary reason to
  `verification-artifact-missing`. The reason-code string may be a public contract, so this needs a
  deprecation window.

## [v0.12.6] — 2026-06-26 · ADR 0007 Retrieval Decision

### Added
- **ADR 0007 — Retrieval Backend Decision** (`docs/adr/0007-retrieval-backend-decision.md`,
  *Accepted*). Decides the retrieval ranking + no-answer policy from the four measured retrieval-v1
  candidates (lexical baseline, threshold t2/t3, BM25, BM25+threshold): selects **BM25 +
  lexical-confidence threshold (t2/t3)** for the project retriever as an ADR 0006 §4.5 internals
  change. It states why BM25-alone (false-support stays 1.0) and threshold-alone (ranking unchanged)
  are each insufficient, preserves the portable-retriever constraints and stable occurrence identity,
  selects **no** RAG/vector/index backend, mints **no** edition-backed assurance, records q010
  broad-thematic recall as unresolved, and defines the implementation scope. Default retrieval is
  unchanged; the default ranking flip is gated on the ≥2-judge + κ step (retrieval-v1.md decision
  gate 2).

### Non-goals
- No retriever implementation change, no RAG/vector/hybrid/built-index/network backend adoption, no
  portable retriever change, and no edition-backed assurance. ADR 0007 records the decision and
  follow-up gates; it does not flip default retrieval behavior on merge.

## [v0.12.5] — 2026-06-26 · BM25 + Threshold Retrieval Experiment

### Added
- Experiment-only **BM25 + lexical confidence threshold** candidate for the retrieval-v1 benchmark
  (`--candidate lexical-bm25-threshold --threshold {2,3}`). BM25 still only re-ranks inside the
  benchmark harness; the confidence gate uses the v0.12.3 lexical threshold semantics, so the t2/t3
  cutoffs are applied to the project retriever's lexical top score rather than to BM25's
  floating-point score scale. Committed Markdown + JSON reports under
  `docs/benchmarks/results/retrieval-v1-lexical-bm25-threshold-t{2,3}.{md,json}`.

### Findings
- BM25+t2 and BM25+t3 preserve BM25's ranking gains over the lexical baseline (MRR 0.938 → 0.969;
  nDCG@5 0.902 → 0.919), keep exact-span hit rate at 1.000, and inherit the threshold experiment's
  no-answer behavior (no-answer correctness 1.000; false-support 0.000).
- The combined candidate still does **not** improve q010 broad-thematic recall (recall@5 remains
  0.25), so lexical ranking plus a confidence gate does not solve that weakness on retrieval-v1.
- No backend is selected and default retrieval remains unchanged; ADR 0007 remains deferred until
  these measured candidates are compared as a decision.

### Non-goals
- No RAG, vector store, dense/hybrid, local index, backend adoption, or default retrieval behavior
  change; no edition-backed assurance; ADR 0007 is **not** written.

## [v0.12.4] — 2026-06-26 · BM25 Retrieval Experiment

### Added
- Experiment-only **BM25-style lexical re-ranking** candidate for the retrieval-v1 benchmark
  (`--candidate lexical-bm25`, with configurable `--k1` / `--b`). It re-ranks the same file corpus
  over the **same tokenization** as the lexical baseline — so the comparison isolates term weighting
  (TF saturation + length normalization + IDF) from tokenization — and is computed entirely in the
  benchmark harness; the portable/project retriever is unchanged. Committed Markdown + JSON reports
  under `docs/benchmarks/results/retrieval-v1-lexical-bm25.{md,json}`, plus benchmark tests for
  tokenization parity with the retriever, identity / citation-fidelity preservation, cross-process
  determinism, CLI validation, and committed-report reproducibility.

### Findings
- On C0, BM25 (Lucene-style defaults: k1=1.2, b=0.75) improves some ranking metrics over the
  lexical baseline (MRR 0.938 → 0.969; nDCG@5 0.902 → 0.919) and preserves exact-span hit rate
  (1.000).
- BM25 does **not** fix the targeted broad-thematic weakness (q010 stays recall@5 = 0.25) or
  no-answer discrimination (false-support remains 1.0). Threshold t2/t3 remain better for
  no-answer because they return no support for the two no-answer probes.
- The candidate preserves stable occurrence identity and 100% citation fidelity (hard constraints
  1–2), and the run is byte-reproducible across processes.
- No backend is selected; the retrieval backend decision (ADR 0007) stays deferred, now informed by
  three reference runs (baseline, threshold, BM25).

### Non-goals
- No RAG, vector store, dense/hybrid, local index, or backend adoption; no default behavior change;
  no edition-backed assurance; ADR 0007 is **not** written.

## [v0.12.3] — 2026-06-25 · Threshold Experiment & Community Feedback Intake

### Added
- Added an experiment-only lexical confidence threshold candidate for retrieval-v1.
- Evaluated thresholds 1, 2, 3, and 5 against the v0.12.2 lexical baseline.
- Committed Markdown and JSON threshold result reports under `docs/benchmarks/results/`.
- Added GitHub issue templates for bug reports, feature requests, corpus/source suggestions, and
  retrieval benchmark issues.
- Added local good-first-issue drafts and a pinned retrieval roadmap draft.

### Findings
- Thresholds 2 and 3 eliminated both no-answer false-support cases without answerable-query
  regression.
- Threshold 5 regressed q007 and q010.
- Default retrieval behavior remains unchanged.
- No backend is selected.

### Non-goals
- No RAG, vector store, BM25, local index, or backend adoption.
- No default threshold behavior change.
- No edition-backed assurance.

## [v0.12.2] — 2026-06-24 · Retrieval Benchmark Lexical Baseline

### Added
- **Retrieval benchmark v1 — lexical baseline measured (`scripts/run_retrieval_benchmark.py`):** the
  first reproducible run of the [retrieval-v1](docs/benchmarks/retrieval-v1.md) benchmark against the
  project (file-based, lexical) retriever. Adds a frozen 18-query set across 8 categories
  (`docs/benchmarks/queries/`), graded relevance judgments keyed on the stable
  `(tradition, work, locator)` identity (`docs/benchmarks/judgments/`), a standard-library-only,
  offline, deterministic runner, and the committed baseline report
  (`docs/benchmarks/results/retrieval-v1-lexical-baseline.{md,json}`). It measures retrieval
  (Recall/Precision/nDCG@1/3/5, MRR, exact-span hit rate, no-answer correctness, false-support),
  contract, and operational metrics. Findings: exact-lookup and character-overlapping paraphrase are
  strong (exact-span hit 1.0, MRR 0.94, recall@5 0.94); broad thematic queries and no-answer
  discrimination are weak (no relevance threshold, so off-corpus queries surface noise-floor false
  positives). **Selects no backend** — backend selection stays deferred to a future decision ADR
  comparing candidates against this baseline. CI gains `--check-fixtures`;
  `tests/test_retrieval_benchmark.py` pins the fixtures, runner determinism, and baseline freshness.
  - **Measured through the contract, not internals.** Candidates are acquired via the retriever's
    per-tradition `retrieve_envelope()` (ADR 0006 §2) and fed — as the **real** envelope, carrying
    the retriever's own `contract_version` — through the **real** B1 adapter, so the contract metrics
    measure what the contract emits (every retrieved record mints a stable `occ/v1-corpus-stable` id;
    required envelope fields; deterministic repeat), not a hand-built parse. The harness is the
    **lexical baseline** and refuses any non-`*-file` `retriever_kind`, so a future index/hybrid/
    dense/service backend (which satisfies the contract but has no comparable `score()`) is measured
    by the deferred backend-selection harness rather than silently mismeasured here.
  - **Citation fidelity is measured, not assumed:** the occurrence id of every returned+relevant
    record is compared across two adapter runs **and** a reordering of the result list (1.0 on the
    baseline; a backend that made identity order-dependent would score below 1.0 and be disqualified).
  - **Concrete span-assurance status** (no tier minted at retrieval; the artifact-backed
    `source_assurance` floor is; edition-backed explicitly false) replaces the prior prose note.
  - **Judging provenance disclosed** (`judgments/…json` → `judging`, surfaced in every report): the
    baseline is a single-curator pass (`independent_judge_count: 1`, IAA `n/a` — disclosed, not
    fabricated); ≥2 independent judges + an inter-annotator-agreement (κ) figure are scoped to the
    deferred decision gate where a candidate is compared against the baseline.
  - CLI rejects non-positive `--k` (no more `ZeroDivisionError`).

## [v0.12.1] — 2026-06-23 · Retrieval Benchmark Definition

### Added
- **Retrieval benchmark v1 definition (`docs/benchmarks/retrieval-v1.md`):** the A2→A3 gate
  [ADR 0006](docs/adr/0006-retriever-fork-contract.md) §6 defers to (its migration phase 5). Defines
  the evidence bar a non-lexical backend (local index / hybrid / dense-vector / RAG service) must
  clear before the *project* retriever may adopt it — the hard constraints any candidate must
  preserve (envelope contract, ADR 0005 stable occurrence identity, the stdlib-only portable
  retriever staying lexical, artifact lifecycle, the A2 rights gate, no edition-backed-assurance
  claim), the evaluation design (curated/full-text corpus tiers, a frozen query set + graded
  relevance judgments, candidate families, retrieval + operational + a citation-fidelity metric, a
  reproducible protocol), and the decision gates (beat the lexical baseline by a pre-registered
  margin *and* pass every hard constraint, else the file-based lexical retriever stays). It **selects
  no backend** and runs nothing; running it and the backend-selection ADR that cites the run remain
  deferred.

## [v0.12.0] — 2026-06-23 · Retriever Contract Fork & A2 Readiness

### Added
- **ADR 0006 — retriever fork + shared contract (A2 readiness):**
  `docs/adr/0006-retriever-fork-contract.md` retires the byte-identical `retrieve.py` invariant in
  favor of a shared **retrieval-envelope contract** that a *portable* (stdlib-only, file-based) and a
  *project* retriever must both pass via a conformance suite. It fixes the load-bearing split between
  what the **retriever** emits (the `religion-council/retrieval/v1` envelope + stable-identity inputs +
  carried provenance) and what the **adapter** mints downstream (`artifact_id` / `span` /
  `occurrence_id`, ADR 0003/0005), so a future index/RAG backend cannot weaken B1/B2/B3/P1. Adds a
  declared `capabilities()` block with the invariant `supports_network_acquisition ⇒
  supports_stable_occurrence_identity`, keeps `contract_version` unchanged (it is the adapter's
  accepted version), and forbids backend selection / edition-backed assurance / dropping the portable
  retriever until a later benchmark ADR.
- **Shared contract-conformance suite (`tests/retrieval_contract/`):** a single battery
  (`contract_assertions.py`) run against a retriever exercises the retriever-level contract over the
  live curated corpus (envelope shape + `contract_version`, required fields, NFC/LF-canonical text,
  capability metadata, determinism, provenance/rights preservation, stdlib-only imports) and the
  identity-level contract over six fixtures fed through the real B1 adapter (deterministic ids,
  duplicate-text distinctness vs. correct same-locator collapse, NFC/NFD + CRLF/LF identity
  stability, fail-closed on underspecified dynamic acquisition, empty-envelope and malformed-record
  behavior). The portable retriever gains an additive `capabilities()` function and `--capabilities`
  CLI (both distribution copies stay byte-identical); existing `retrieve()` / `retrieve_envelope()`
  behavior is unchanged.
- **Project retriever entry point (`orchestrator/project_retrieve.py`):** the project-side retriever
  the orchestrated council uses, still file-based — a thin wrapper over the portable retriever that
  emits the same `religion-council/retrieval/v1` envelope and stable-identity inputs, reports
  `retriever_kind=project-file`, and passes the same contract suite (plus an explicit
  semantic-equivalence check against the portable retriever). It MAY later grow a local index / RAG
  client, changing only its internals and `retriever_kind`, never the contract or the downstream
  B1/B2/B3/P1 guarantees. No index/RAG/network backend is selected.

### Changed
- **Byte-parity retired as the cross-implementation retriever gate (ADR 0006 phase 4):**
  `tests/test_retrieve.py`'s parity test is reframed as a **narrow same-artifact** check between the
  two *portable* `retrieve.py` copies only; cross-implementation consistency (portable ↔ project) is
  now guaranteed by the contract suite, and a new test asserts the project retriever shares the
  contract (not bytes). README and `docs/CORPUS.md` parity language updated (EN + ZH) to point at
  the conformance suite and ADR 0006.

## [v0.11.0] — 2026-06-22 · Stable Evidence Identity & Corpus Baseline

### Added
- **ADR 0005 — stable occurrence identity (A1):** the adapter now mints occurrence ids under three
  explicit, versioned schemes (`occ/v1-corpus-stable` / `-network-stable` / `-index-fallback`),
  records the scheme on each seed and in the origins log, and **fails closed**
  (`StableIdentityError`) when a network/dynamic acquisition (`runtime-captured`) lacks stable
  identity inputs (`record_key`, or `work`+`locator`, or `source_file`+`source_line`) — refusing an
  order-dependent id before persistence and before claim binding. Origin hints must be a non-empty
  path AND a positive line number, so degenerate values (`""` / `0`) cannot bypass the gate.
  Existing corpus-stable and index-fallback id bytes are unchanged (no silent migration);
  file-based retrieval is unaffected. `docs/CORPUS.md` corrected: `source_file` / `source_line`
  are not Artifact identity but DO seed the legacy occurrence scheme.
- **A1 public-domain corpus enrichment (S3):** every tradition raised to a uniform baseline of 7
  records (38 → 56), fixing balance (no tradition below the project median). Every new record
  carries a per-snippet provenance + rights-basis note in `presentation.json`: classical-Chinese
  and `和合本` 1919 excerpts assert a public-domain basis (by age / publication date), Qur'an (馬堅
  釋義) and Sanskrit→Chinese additions are marked renderings, and none is labeled edition-backed.
  The public-domain basis is **asserted, not independently audited** per edition/jurisdiction —
  every note defers to redistribution review. New curation tests cover per-snippet rights presence
  + honest scoping, enum validation, NFC/LF, span integrity, snapshot + occurrence-id
  reproducibility, no orphan curation, and dual-copy (portable / `.claude`) parity.

## [v0.10.0] — 2026-06-22 · Safety routing, corpus inventory & assurance footer

### Added
- **Canonical crisis-first safety routing (S1):** `policies/safety-routing.v1.json` is the single
  source for crisis-first handling, with a conformance test (`tests/test_safety_routing.py`) that
  every distribution surface (DISCLAIMER, README, both skills, the moderator agent) carries the
  rule and none silently omits it. The controller enforces the one machine guarantee — a request
  already classified crisis-first cannot enter the council pipeline (`guard_crisis_routing`;
  `DebateController.start(crisis_classification=...)`) — without claiming any natural-language
  crisis *detection*, which stays a distinct, fallible, out-of-scope boundary.
- **Reproducible corpus inventory (S2):** `scripts/corpus_inventory.py` (`--format text|json`,
  `--check`) reports deterministic per-tradition and overall metadata counts from the same records
  the portable retriever returns, and flags structural/policy-invalid records. `--check` fails only
  on violations, never on count changes, and runs in CI.
- **Deterministic assurance footer (S4):** `orchestrator/assurance_footer.py` renders a
  user-visible authority-assurance summary counted only from finalized state (curated-snapshot vs
  edition-backed vs source-bound, denied claims, always-visible interpretation limitation); never
  labels a curated span as edition-backed. Exposed additively on each `debate_finalize` result.

## [v0.9.0] — 2026-06-21 · Strict finalization & traceable authority

### Added
- **ADR 0004 — renderer trust boundary:** the contract of record for the user-facing finalizer:
  authority, interpretation, and audit channels; provenance-defined (not semantically classified)
  authority; a deterministic authority surface; structured render IR; post-render trace validation;
  and normative invariants for the Axis-B capstone.
- **Renderer finalizer:** `render_types.py` provides frozen `AuthorityRenderUnit` values minted
  only through the canonical builder's capability token. `render_finalizer.py` supplies the
  canonical authority-unit builder, deterministic Surface A serializer, non-removable Surface B
  framing, independent `TRACE_*` render-time trace validator, system-authoritative representation
  cross-check, atomic `finalize`, and `validate_strict_profile`.
- **Strict controller workflow:** `profile="strict"` fails fast unless the
  structured → verify → fail-closed → finalize graph is complete. `debate_finalize` builds Surface
  A only from admitted claims; quotation text is taken from the canonical snapshot span, never
  producer text. Existing `collect()` behavior remains backward compatible.
- **Finalization state machine:** a strict run exposes `finalization_required` and remains
  `finalized=false` until `debate_finalize` succeeds. `collect()` and round summaries never emit a
  finalized authority surface.

### Changed
- **Assurance honesty** in `policies/quote-admissibility.v2.json` (descriptive only, no behavior
  change): `assurance_layers.user_visible_authority_surface` is `implemented` with
  `user_visible_authority_surface_scope: strict-finalized-responses`. The hybrid `mode_assurance`
  states that the renderer boundary is machine-enforced for finalized strict responses while the
  default hybrid prose path (without `debate_finalize`) is unchanged and not finalized.

### Notes
- Strict-finalized responses provide end-to-end machine-enforced construction and traceability of
  the textual-authority surface (Surface A). Interpretation prose (Surface B) remains explicitly
  non-authoritative and instruction-bounded.
- The default hybrid path without `debate_finalize` is unchanged and not finalized. The complete
  answer is not semantically fail-closed; interpretation prose can still mislead; and the mint
  guard is a capability-shaped API guard, not a Python sandbox.

## [v0.8.0] — 2026-06-17 · A1 corpus presentation metadata
### Added
- Curated `references/presentation.json` sidecar carrying per-record `representation_kind` /
  `rendering_mode` / `provenance` / `rights`, merged by `retrieve.py` onto matching records by
  `(tradition, work, locator)` and carried (carried-not-trusted) through the adapter to the
  evidence catalog, so renderings (e.g. the Chinese Qur'an = published-translation +
  meaning-rendering) can be presented with a marker.
### Notes
- Additive and curated-only (nothing inferred). Wrong-typed sidecar values are dropped at merge
  (pure-stdlib type check); enum-membership is asserted in tests. Both `retrieve.py` copies and
  both `presentation.json` copies stay byte-identical. The broader public-domain excerpt expansion
  remains future content + rights work.

## [v0.7.0] — 2026-06-17 · B3 response-boundary fail-closed
### Added
- `response_boundary` fail-closed gate (opt-in `fail_closed`, requires `verify_claims`): a
  pre-renderer default-deny over structured claims producing a per-result `boundary_decision`;
  the only fail-closed rung of the ladder. Manifest gains `boundary_denial_reasons` and the
  `structured-fail-closed` response mode.

## [v0.6.0] — 2026-06-17 · B2 claim-level validation
### Added
- `claim_verification` (opt-in `verify_claims`): each `[Text]` support edge is validated against
  the curated-snapshot tier → `runtime-validated` / `failed`; a failed support edge is removed and
  a `[Text]` that loses all support is downgraded to a non-supporting `unverified-citation`; the
  council continues. Additive — B1b `claim_bindings` stay `unverified`. `EvidenceStore.read_snapshot`
  and the `structured-claim-validated` response mode added.

## [v0.5.0] — 2026-06-17 · B1a + B1b structured evidence seam
### Added
- **B1a:** immutable, content-addressed evidence snapshots and the `RetrievalEvidenceAdapterV1`
  minting occurrence-level `EvidenceSeed`s (schema-level only; verification always `unverified`).
- **B1b:** frozen `religion-council/claim/v1`; the hybrid controller parses panelist payloads,
  schema-rejects malformed ones (retry → repair → drop), binds claims to evidence seeds by
  occurrence-level `evidence_seed_id`, and surfaces a response-level `enforcement_mode`. Opt-in
  (`structured_claims` + `evidence_envelope`); prose mode unchanged.

## [v0.4.0] — 2026-06-16 · Secular voices
### Added
- Secular humanist / liberal (non-religious) perspectives, explicitly marked as non-religious.

## [v0.3.0] — 2026-06-16 · Debate hardening
### Changed
- Claim-level adversarial pressure in the debate prompts; moderator-routed contrast proposition
  (injected into a controller-routed section, evaluated as data, never executed).

## [v0.2.1] — 2026-06-16 · Dual-axis evidence architecture
### Added
- Architecture-of-record for the two axes (A0–A3 / B0–B3) and the retrieval-to-evidence seam
  (ADR 0002, ADR 0003) — terminology and contracts only, no runtime evidence model yet.

## [v0.2.0] — 2026-06-14 · B0 quote-admissibility policy
### Added
- Unified, instruction-enforced quote-admissibility policy (ADR 0001): one canonical manifest
  generating all four surfaces, conformance tests, and hardened panelist prompts.
### Changed
- Removed the "explicitly consulted" loophole; model memory alone never supports `[Text]`;
  evidence/reference packets are untrusted data.

## [v0.1] — 2026-06-14 · Deterministic hybrid council
### Added
- The v0.1 deterministic hybrid panel: a Claude moderator driving one persistent Codex thread per
  panelist, with a complete-round barrier, retries, thread-id reuse, and persisted run records;
  A0 file-based lexical retrieval over the curated `references/`. (Delivery history, not an Axis-A
  stage — it did not change retrieval. See ADR 0002 §3.)
