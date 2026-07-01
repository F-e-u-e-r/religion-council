# ADR 0008 — Corpus Versioning: Textual-Witness & Canon Metadata

- Status: **Proposed** (accepted on merge). This ADR decides the **schema + boundaries only** — no
  corpus record, retriever code, or benchmark report changes here.
- Scope: how a corpus record discloses **which textual witness / recension / canon / commentary
  lineage** it belongs to, carried through the **existing A1 `presentation.json` sidecar**. A
  metadata/provenance decision — **not** a new metadata mechanism, **not** an assurance change, and
  **not** a new corpus record.
- Owner stage: A1→A2 corpus enrichment ([ADR 0002](0002-roadmap-stage-nomenclature.md)).
- Relationship: extends **A1** (the `presentation.json` sidecar — merged per `(tradition, work,
  locator)`, curator-declared and **carried-not-trusted**, [ADR 0003](0003-retrieval-evidence-adapter.md)
  §2); holds the **assurance boundary** of [ADR 0004](0004-renderer-trust-boundary.md); and preserves
  [ADR 0006](0006-retriever-fork-contract.md)'s `version` = *source edition* semantics and portable
  byte-parity.

## Context

- The corpus ships **one recension per work without disclosing which.** e.g. `《道德經》1` is the
  received / 王弼 (通行本) text — «道可道,非常道» — but the record never says so; the 馬王堆帛書
  witness reads «道可道也,非恆道也» (恆 is the pre-Han-taboo original; 常 is the later avoidance
  substitution for 漢文帝 劉恆). Neither is "wrong"; the honest gap is that the witness is **undeclared**.
- **The mechanism to fix this already exists.** The A1 `presentation.json` sidecar merges per-record
  `representation_kind` / `rendering_mode` / `provenance` / `rights` by `(tradition, work, locator)`,
  curator-declared and carried-not-trusted. It already carries **cross-tradition** seed metadata:
  `provenance` / `rights` for all eight traditions, with `representation_kind` / `rendering_mode`
  populated fully only for the Qur'an (`published-translation`) and the Hinduism (`generated-rendering`)
  seeds — the other six are provenance/rights seeds. So the **data** is partial, not the mechanism.
- **`version` drift.** [ADR 0006](0006-retriever-fork-contract.md) and `docs/CORPUS.md` define each
  record's `version` as the **source edition** (e.g. `通行本`), but the runtime retriever emits a
  uniform placeholder `"version": "curated-reference-v0.1"`. This is **contract/documentation drift**
  to be corrected — **not** a completed edition tag, and it must not be dressed up as one.
- Several traditions have a **canon-scope** problem that is *larger and different from* a single work's
  witness variants: the Buddhist canon differs across 南傳/漢傳/藏傳; the Christian canon is 66 / 73 /
  more books (Protestant / Catholic / Orthodox); Islam splits Sunni / Shia hadith; Hinduism has no
  single canon (śruti / smṛti). Same question → different citable corpus.
- The benchmark reports already count provenance metadata (`contract.representation_metadata_records`,
  `contract.rights_metadata_records`), so **filling metadata is visible in the reports** even when
  rankings do not move.

## Decision

1. **Sidecar-first.** Carry all witness / canon / lineage / family metadata through the **existing**
   `presentation.json` sidecar — no parallel metadata system. Fields stay curator-declared and
   carried-not-trusted (ADR 0003 §2). The existing A1 merge drops wrong-typed sidecar values; enum
   membership is enforced by curation/schema tests and must not silently ship unknown values.

2. **Two orthogonal axes — split, never conflate.** A record's *textual witness type* and its
   *scriptural canon* are different questions and take different fields:
   - `witness_kind`: `received | excavated | dunhuang_fragment | reconstructed | …` — what kind of
     witness the text is.
   - `canon_scope`: `protestant | catholic | orthodox | sunni | shia | theravada | mahayana |
     vajrayana | …` — which canon / tradition scope the record belongs to.

   With three supporting fields:
   - `textual_witness`: `wang_bi | heshang_gong | mawangdui_a | mawangdui_b | guodian_a | beida |
     fuyi_guben | xianger | …` — the specific witness (refines the source-edition `version`).
   - `commentarial_lineage`: `wang_bi | heshang_gong | xianger | zhu_xi | none | …` — the
     reading/commentary tradition, **distinct** from the base text. This is how 王弼 vs 河上公 are
     modeled: two lineages over one received-text **family**, not two "sects".
   - `corpus_family`: `daodejing | yijing | bible | quran | pali_canon | taisho | …` — groups
     witnesses of one work.

3. **Assurance boundary (unchanged).** `edition_assurance` may be *reserved* as a field, but the
   **default stays the honest floor** the repo already mints — artifact-backed / curated-snapshot.
   `edition-backed-span-verified` **must not be claimed** until real byte/span verification against a
   **named** edition exists; ADR 0004 forbids overstating authority and ADR 0006 keeps edition-backed
   assurance at A2. **A metadata field must never imply a verification that was not performed** — the
   same principle as the retrieval-v1 κ gate guardrail.

4. **`version` semantics resolved.** `version` is the **source edition** (ADR 0006). Phase 1 fixes the
   `curated-reference-v0.1` placeholder honestly — a real per-record edition/witness tag, or the
   witness carried via the sidecar — **without** implying edition-backed assurance.

5. **`corpus_family` drives retrieval diversity — it is not display-only.** Once more than one witness
   of the same line exists, retrieval must **de-duplicate / group by family** (at most one witness per
   family in top-k, or an explicit grouped result), so a query like «道» is not flooded by
   near-identical 道德經 witnesses that crowd out other traditions. The *policy* is fixed here; it is
   *enforced* in Phase 2 (when multiple witnesses first appear).

6. **Phased rollout.**
   - **Phase 1 — metadata-only, no new records.** Extend the sidecar schema + enum-membership tests;
     backfill the existing 56 records conservatively (most = `original-text` / `received` / classical
     Chinese); resolve `version`. **Rankings / candidate metrics do not change**, but committed reports
     **may** change (`representation_metadata_records`, `rights_metadata_records`, `corpus_version`) and
     MUST be regenerated with an assertion that rankings/metrics are unchanged and only
     provenance/contract counts differ.
   - **Phase 2 — tracked corpus bump, one tradition at a time.** A **new witness record** (e.g. 帛書,
     河上公) is a **corpus-version bump**: regenerate reports, add relevance judgments for the new
     record, and apply family de-dup. Sourcing (which scholarly edition the witness is transcribed
     from) is recorded in `provenance`; rights are reviewed per `docs/CORPUS.md`.

7. **Risk tiering (Phase-2 order).**
   - **A — canon scope first:** 佛教 (南傳/漢傳/藏傳), 基督宗教 (66/73/+ canon; plus translation, e.g.
     和合本/思高本), 伊斯蘭 (Sunni/Shia hadith; the Qur'an stays a `meaning-rendering`, **never** a
     textual "version"), 印度教 (śruti/smṛti boundary). Their primary axis is **`canon_scope`**, not
     witness variants.
   - **B — witness / commentary:** 道教 (道德經 witnesses; 莊子/列子/參同契 issues), 儒家 (經學/注疏:
     春秋三傳, 周易 王弼/程/朱, 四書朱注 vs 陽明).
   - **C — reserve metadata, simplify:** 法家 (authenticity/attribution), 墨家 (chapter groups:
     十論 / 墨辯 / 守城 — grouped so retrieval does not blend ethics, logic, and siege craft).

## Consequences

- The repo can present **multiple recensions as separate, disclosed voices that argue with each other**
  (aligned with the Council's "plural, not flattened" ethos) — without privileging one text or minting
  assurance it has not earned.
- Phase 1 is safe and reversible (metadata only). Phase 2 is deliberate and staged (each new witness is
  a tracked corpus change with its own report regeneration + judgments).
- Forks can extend witnesses / canons for their own needs on top of a stable, disclosed schema.

## Acceptance criteria (for the Phase 1 PR that follows)

- Sidecar schema extended; enum membership checked in the test suite; wrong-typed sidecar values stay
  dropped at merge and unknown enum values must not silently ship.
- Both `presentation.json` copies stay byte-identical (`test_presentation_sidecars_are_byte_identical`);
  if `retrieve.py` is touched, both copies stay byte-identical
  (`test_portable_distribution_copies_are_byte_identical`); the project retriever still wraps / inherits
  portable metadata behavior.
- `version` placeholder resolved to source-edition semantics; **no `edition-backed-span-verified`
  claimed**.
- If emitted metadata changes: reports regenerated; **rankings / candidate metrics unchanged**; only
  provenance/contract counts + `corpus_version` differ.
- No new corpus records; no ranking behavior change; no BM25 default flip; no RAG/vector/index/network
  backend; no change to the curator-1 scoring set.

## Non-goals

- No new textual-witness **records** (that is Phase 2).
- No edition-backed assurance minted or implied.
- No retrieval ranking change / BM25 default flip.
- No RAG / vector / index / network backend.
- No change to the curator-1 scoring set or the retrieval-v1 benchmark metrics.
