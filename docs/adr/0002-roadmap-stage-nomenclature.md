# ADR 0002 — Roadmap Stage Nomenclature and Enforcement Ladder

- Status: Accepted
- Scope: terminology and architecture-of-record only. This ADR introduces **no**
  runtime evidence model, parser, validator, renderer, or fail-closed controller.
- Relationship to ADR 0001: **partially supersedes ADR 0001 for roadmap-stage
  terminology only** (its decisions 9–10 named stages "P0" and "P3–P4"). The
  substantive quote-admissibility policy of ADR 0001 is unchanged and remains in force.

## Context

The project was described with three overlapping numbering schemes at once: an Axis-A
`Phase 0 / 0.5 / 1 / 2 / 3` scale, an Axis-B `B0–B3` scale, and a delivery `P0 / PR1 /
PR2 / PR3 / P4` scale. These did not line up: B0 was called both "P0" and "PR1",
fail-closed was called "P3–P4" in ADR 0001 and the policy manifest but "P4" in the
roadmap, and "Phase 2" (Axis A) collided with "B2" (Axis B) despite being different
milestones. The manifest still embedded `P3–P4`, `P4`, and `PR2+` in its descriptions.

The two axes are **low-coupling, not independent**. They share a seam: the retrieval
result is converted, through a single adapter, into the evidence model the
admissibility axis enforces (see [ADR 0003](0003-retrieval-evidence-adapter.md)).

## Decision

### 1. Two architecture-stage scales, and only two

Public architecture stages are:

- **Axis A — corpus & retrieval: `A0`–`A3`.**

  | Stage | What | Retrieval |
  |---|---|---|
  | **A0** | Curated council: voices quote hand-picked, cited snippets in `references/`. Offline, any agent. | File parse + lexical ranking. |
  | **A1** | Deeper curated corpus: expand `references/` and `01–08/典籍清單.md` + `思想概要.md` with more public-domain / openly-licensed excerpts + provenance. v0.8.0 ships the presentation/provenance/rights metadata foundation and first curation seed; broader excerpt growth remains rights-reviewed content work. | Still file-based. |
  | **A2** | Full 典籍 + local index: store complete open scriptures in-repo, chunked; benchmark lexical / cross-lingual / dense / hybrid; build the chosen index. | Local index — same retrieval envelope contract. |
  | **A3** | Networked RAG service: index behind a retrieval service; `retrieve.py` becomes a thin client. | Networked — same contract. |

- **Axis B — admissibility & enforcement: `B0`–`B3`.** (See the ladder below.)

### 2. PR numbers are delivery history, never stage names

`PR1`, `PR2`, … record *when* something shipped. They are not architecture stages and
must not appear as stage names in the roadmap, ADRs, or the policy manifest. The old
`P0`, `P3–P4`, and `PR2+` shorthands are retired; where they carried meaning they map to
B-stages.

### 3. Old "Phase 0.5" is delivery history, not an Axis-A stage

The v0.1 deterministic hybrid panel (Claude moderator + persistent Codex panelists, the
controller with barriers/retries/records) did **not** change retrieval — it stayed
file-based. It therefore consumes no Axis-A stage number. It is the controller milestone
the B-axis builds on, recorded in the changelog, not in `A0–A3`.

### 4. Axis-B stages

- **B0 — unified instruction-enforced policy.** Completed. One policy source generates
  four surfaces; "explicitly consulted" loophole removed; model memory alone never
  supports `[Text]`; packets are untrusted data. Hybrid mode is instruction-enforced and
  **not** fail-closed. (This is ADR 0001's policy.)
- **B1 — structured claim protocol + stable evidence seam.** Panelists emit a versioned
  structured claim protocol; the `RetrievalEvidenceAdapterV1` mints stable `Artifact` /
  `Span` identity from a versioned retrieval envelope. Schema-level rejection only;
  B1's initial `VerificationResult` is always `unverified`. (See ADR 0003.)
- **B2 — claim-level evidence validation.** Each `[Text]` claim gains `runtime-validated`
  or `failed`; the failed `[Text]` *support edge* is removed (a non-supporting
  `unverified-citation` may be retained where policy allows) and the council degrades
  gracefully.
- **B3 — response-boundary fail-closed.** Unknown claim types, unstructured-evidence
  bypass, renderer bypass, and unsupported protocol versions are default-denied before
  the user-facing renderer.

### 5. The enforcement ladder is three distinct rejections

"Reject" means something different at each stage; conflating them is the confusion this
ADR removes. The controller is **not** fail-closed until B3, even though B1 and B2
already reject things, because B1/B2 *repair or drop a single claim and continue* whereas
B3 *denies at the boundary by default*.

| Stage | Rejects | Action | Scope |
|---|---|---|---|
| **B1** | malformed structured payload | retry / repair | schema enforcement only |
| **B2** | inadmissible evidence on a `[Text]` claim | remove the `[Text]` support edge; keep a non-supporting `unverified-citation` where policy allows; council continues | claim-level validation |
| **B3** | unknown claim type, unstructured-evidence bypass, renderer bypass, unsupported protocol | default-deny before the renderer | response-boundary fail-closed |

### 6. User-visible assurance

This is a **future B-stage requirement — not in force at B0 and not implemented in this
PR.** From B1 onward a rendered response should show its **response-level enforcement
mode**, and from B2 onward every `[Text]` claim should show its own **verification /
assurance qualifier**, so that an instruction-only citation (Claude-only / portable, or
hybrid before B3) is not mistaken for a runtime span-verified one. B0 renders neither — the
generator emits only claim markers and rules. Span-verification assurance is itself tiered — a
`curated-snapshot-span-verified` claim only matches the project's ingested snapshot,
while `edition-backed-span-verified` (A2+) is tied to edition provenance. (Tiers defined
in ADR 0003 and `policies/quote-admissibility.v2.json`.)

### 7. Per-mode enforcement remains asymmetric

Hybrid mode reaches runtime-enforced / fail-closed at B3. Claude-only and portable modes
stay instruction-enforced unless a structured adapter + validator is later provided for
them. Decision 6's user-visible qualifier is how a reader tells which assurance they got.

## How this lands in the repo

- `policies/quote-admissibility.v2.json` carries the B0–B3 stage model, the enforcement
  ladder, and the user-visible-assurance requirement; v1 is marked superseded.
- ADR 0001's normative body is **not** rewritten; it gains only a one-line note that its
  stage terminology (decisions 9–10) is superseded here.
- The README and `docs/CORPUS.md` roadmaps are restated on the A/B scales.

## Non-goals

- No runtime `Artifact` store, `Claim` parser, span validator, admissibility engine,
  renderer, or fail-closed controller. Those are B1 (runtime) / B2 / B3 implementation,
  not this ADR. This ADR is nomenclature and architecture-of-record.

## Status after this ADR

> Architecture stages are A0–A3 and B0–B3; PR numbers are delivery history only. The
> enforcement ladder (schema reject → support-edge removal → boundary fail-closed) is named but not
> yet implemented; hybrid mode remains instruction-enforced and is not fail-closed.
