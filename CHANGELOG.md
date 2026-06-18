# Changelog

All notable changes to this project are documented here. Entries are grouped by release tag and
framed around the project's two architecture axes (see
[ADR 0002](docs/adr/0002-roadmap-stage-nomenclature.md)):

- **Axis A — corpus & retrieval:** `A0`–`A3`
- **Axis B — admissibility & enforcement:** `B0`–`B3`

The format is adapted from [Keep a Changelog](https://keepachangelog.com/); versions follow
`vMAJOR.MINOR.PATCH`. (The first tag `v0.1` predates that convention and is kept as-is.)

## [Unreleased]

### Added
- **ADR 0004 — renderer trust boundary** (P0): the contract of record for the user-facing
  finalizer — authority/interpretation/audit channels, provenance-defined (not semantically
  classified) authority, a deterministically-built authority surface, a structured render IR,
  post-render trace validation over render units, and seven normative invariants.
- **Renderer finalizer (P1):** `render_types.py` (frozen `AuthorityRenderUnit` minted only via the
  canonical builder's capability token) and `render_finalizer.py` (canonical authority-unit builder;
  deterministic Surface A serializer; non-removable Surface B framing; independent trace validator
  with `TRACE_*` render-time `renderer-bypass` reasons; representation system-authoritative
  cross-check; atomic `finalize`; `validate_strict_profile`).
- **Controller (P1):** `profile="strict"` configuration invariant (fails fast if the
  structured→verify→fail-closed→finalize graph is incomplete; never degrades to B0) and a new
  `debate_finalize` entry + MCP tool that builds Surface A only from admitted claims. Quotation
  text is sourced from the snapshot span (never producer text). `collect()` is unchanged.
- **Workflow invariant (P1):** a `profile="strict"` run carries `finalization_required` and is not
  `finalized` until `debate_finalize` succeeds; `collect()` / round summaries surface this and never
  emit a finalized authority surface — only `debate_finalize` does.

### Changed
- **Assurance honesty** in `policies/quote-admissibility.v2.json` (descriptive only, no behavior
  change): `assurance_layers.user_visible_authority_surface` is now `implemented` with
  `user_visible_authority_surface_scope: strict-finalized-responses`; the hybrid `mode_assurance`
  states the renderer boundary is machine-enforced for finalized / `profile=strict` responses while
  the default hybrid prose path (no `debate_finalize`) is unchanged and not finalized.

### Notes
- The interpretation surface (free panelist prose) remains instruction-bounded and explicitly
  non-authoritative — its semantic correctness is **not** a machine guarantee.
- Deferred follow-up: renaming the older controller `renderer-bypass` boundary reason to
  `verification-artifact-missing` (a reason-code string may be a public contract, so it warrants a
  deprecation window).

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
