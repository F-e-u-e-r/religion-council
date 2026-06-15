# ADR 0003 — Retrieval-to-Evidence Adapter and Immutable Snapshot Lifecycle

- Status: Accepted
- Scope: contract and lifecycle of record only. This ADR specifies the seam where Axis A
  (retrieval) meets Axis B (admissibility). It introduces **no** runtime implementation:
  no Artifact store, no `Claim` parser, no span validator, no admissibility engine, no
  renderer, no fail-closed controller.
- Owner stage: **B1** (see [ADR 0002](0002-roadmap-stage-nomenclature.md)).

## Context

Axis A and Axis B are low-coupling but meet at one point: the retrieval result must be
converted into the evidence model the admissibility axis enforces. That converter — the
`RetrievalEvidenceAdapter` — is the load-bearing piece, and it is the first place a
*stable* `Artifact` / `Span` identity is required.

The current retrieval contract exposes only `source_file` and `source_line` as
provenance, and `docs/CORPUS.md` already classifies both as **implementation metadata
that downstream code must not depend on**. A line number in a hand-edited Markdown file
is not a durable identity: A1 actively churns those files, so any identity derived from a
live line number shifts on every edit. The adapter therefore cannot pass `source_line`
through as identity — it must mint identity from immutable bytes.

This requirement lands at **B1**, when identities are first *minted and persisted*, not
at B2 when they are first *verified*. A `Span` persisted at B1 with
`verification = unverified` still needs a stable artifact to point at.

## Decision

### 1. `RetrievalEvidenceAdapterV1`

- **Owner:** B1.
- **Input:** a versioned retrieval envelope (`retrieve_envelope()` →
  `{ "contract_version": "religion-council/retrieval/v1", "records": [...] }`). The
  adapter trusts only `contract_version` for shape negotiation. The legacy `retrieve()`
  list remains for existing callers and is not the adapter's input. Each record's `text`
  **is** the canonical bytes the adapter content-addresses (see §4), so the envelope is
  self-sufficient for identity without `source_file` — the contract need not change when
  the backend becomes a network service at A3.
- **Output (conceptual seed):** `Artifact`, `Span`, `Claim`, `ClaimEvidenceEdge`, an
  initial `VerificationResult`, plus provenance and assurance metadata.
- **The adapter does not decide admissibility.** It produces structured evidence; whether
  a claim is quote-admissible is a *validator* decision under the named policy at B2+, not
  a flag the adapter or the producer sets.

### 2. Producer-declared metadata is carried, not trusted

The retrieval contract already carries `label`, `evidence_type`, and `verbatim`. The
adapter **reuses their canonical semantics** but treats them as **producer-declared
metadata, not verified facts**. They seed the structured claim; they do not by themselves
establish verification or admissibility.

### 3. Initial verification is always `unverified`

Every `VerificationResult` the B1 adapter emits is fixed at `unverified`. Only B2's
claim-level validation may transition a result to `runtime-validated` or `failed`. B1
performs schema-level rejection only.

### 4. Immutable snapshot lifecycle

The immutable bytes the adapter content-addresses are the retrieval record's own `text`
field — **not** the live `.md` file and **not** `source_file` / `source_line` (which do
not exist under A3 network retrieval). The envelope therefore carries everything needed to
mint identity, backend-independently; at A2/A3 a record MAY additionally carry an additive
`artifact_ref` + `content_hash` + `span` for the stronger edition-backed tier. `Artifact` identity
is **never** a hash computed on the fly from a live file. Ingest copies those bytes into an
immutable, content-addressed store:

```text
retrieval record `text`  (A0–A1)   /   artifact_ref + content_hash  (A2–A3)
        │  ingest: copy bytes out
        ▼
immutable copied snapshot   (decoupled from later edits to the source)
        │
        ▼
content hash → artifact_id
        │
        ▼
stable byte span (selector into the snapshot)
```

Rules:

1. Ingest **copies** artifact bytes (the record `text`, or the A2/A3 `artifact_ref`
   target) into a persistent evidence store; it does not reference any live file's
   current contents.
2. **Canonical bytes are pinned so every backend hashes identically:**
   `snapshot_bytes = UTF-8( NFC( record.text ) )` with newlines normalized to `LF`;
   `artifact_id = sha256(snapshot_bytes)`; a `Span` selector is a **byte offset + length
   over `snapshot_bytes`**. Without this, A2/A3 backends could hash the same wording
   differently (encoding, Unicode normalization, or line endings). At A0/A1 the artifact
   *is* `record.text`, so the span is the whole snapshot. At A2/A3 an `artifact_ref` may
   point to a canonical unit **larger** than the quote (e.g. a chapter): `artifact_ref` +
   `content_hash` identify that unit under the **same** canonicalization, but they do
   **not** locate the quote — so the record MUST also carry the `Span`
   (`byte_offset` + `byte_length`), since identical wording can occur more than once.
3. A `Span` selector points into the **snapshot**, never into the live file.
4. Editing a reference file (an A1 activity) and re-ingesting **mints a new artifact
   version**. It does not mutate or invalidate the prior snapshot.
5. Old snapshots are **never overwritten or deleted**; spans already verified against them
   remain valid.
6. `source_file` and `source_line` are retained only as **ingest hints / origin
   metadata**. They never participate in persistent identity.
7. The Git commit / blob of the ingested file may additionally be recorded to aid source
   reproduction.

### 5. Span-verification assurance is tiered

A verified span is not uniformly strong. Two tiers, kept distinct:

- **`curated-snapshot-span-verified`** — the span deterministically matches the immutable
  snapshot the project ingested. It proves fidelity to *our snapshot*, **not** to any
  published edition. Available once B2 verifies against snapshots built from today's
  curated references.
- **`edition-backed-span-verified`** — the span is verified against a canonical text unit
  carrying edition provenance. The stronger tier. Available at **A2**, when such units
  exist.

B2/B3 may therefore ship on the curated-snapshot tier **without waiting for the full A2
corpus**; the assurance qualifier (ADR 0002 §6) tells the reader which tier a claim
holds.

### 6. Evidence dimensions are orthogonal; role is claim-relative, not authorization

The evidence dimensions each answer exactly one question and are kept separate.
**`evidentiary_role`** (`primary-source` / `secondary-source` / `unknown`) is
*claim-relative* and lives on the **`ClaimEvidenceEdge`**, not on the `Artifact` — the same
transcript can be the primary source for a "what panelist X said" claim yet not support a
scripture claim at all. **`artifact_kind`** (`source-text` / `secondary-literature` /
`reference-summary` / `debate-transcript` / `issue-matrix` / `unknown`) is the artifact's
intrinsic type. Supply/capture origin is **`acquisition_origin`** (`bundled` /
`user-supplied` / `runtime-captured` / `model-asserted` / `generated-in-session`); whether
it came through the retrieval seam this run is the separate **`retrieval_path`** (a bundled
snippet is commonly *also* retrieved — independent axes). None of these authorizes
quotation; admissibility stays a validator-derived decision over the whole tuple plus
`representation_kind`, `source_assurance`, artifact/span availability, verification, and
policy profile. The canonical enums live in `policies/quote-admissibility.v2.json`.

## Consequences

- B1 is unblocked on today's retrieval: the adapter can mint immutable snapshots from the
  existing curated references now.
- The "two independent axes" framing is made honest: A and B are independent up to B1;
  B2/B3 depend on Axis A exposing stable artifact/span identity, satisfied first by the
  snapshot tier and later upgraded by A2's edition-backed tier.
- The canonical span-assurance tiers and the producer-declared-metadata rule are recorded
  in `policies/quote-admissibility.v2.json`.

## Non-goals

- No implementation of the Artifact store, the `Claim` schema parser, the span validator,
  the admissibility engine, the renderer, or controller fail-closed. This ADR fixes the
  contract and lifecycle so those can be built later without drift.
