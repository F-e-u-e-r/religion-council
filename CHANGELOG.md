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
