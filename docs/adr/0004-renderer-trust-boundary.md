# ADR 0004 — Renderer Trust Boundary and the Authority/Interpretation Split

- Status: Accepted
- Implementation status: **Implemented in P1.** P0 landed this ADR + the assurance-honesty
  manifest edits + `CHANGELOG.md` (docs only). P1 landed the runtime: `render_types.py`
  (authority units minted only via the builder's capability token), `render_finalizer.py`
  (canonical authority builder, independent trace validator, deterministic Surface A serializer,
  atomic `finalize`, strict-config validation), and the controller's `profile="strict"` +
  `debate_finalize` entry/tool.
- Scope of the guarantee: machine enforcement applies to the **finalized textual-authority
  surface produced through `debate_finalize`** (and required for `profile="strict"` runs).
  Interpretation prose (Surface B) remains explicitly non-authoritative and instruction-bounded.
  The default hybrid prose path (no `debate_finalize`) is unchanged and is not machine-enforced.
- Owner stage: completes **B3** (response-boundary fail-closed) at the actual user-facing
  surface. Builds on [ADR 0002](0002-roadmap-stage-nomenclature.md) (enforcement ladder),
  [ADR 0003](0003-retrieval-evidence-adapter.md) (evidence identity), and the B1b–B3 +
  A1 implementations.

## Context

B1b–B3 made the structured pipeline real: panelists emit `religion-council/claim/v1`,
`claim_binding` binds claims to occurrence-level evidence seeds, `claim_verification` validates
`[Text]` against the curated-snapshot tier, and `response_boundary` produces a fail-closed
`boundary_decision` over the structured claims. A1 carries curated `representation_kind` /
`rendering_mode` / provenance / rights through to the catalog.

But the **user-facing renderer is the Claude moderator composing prose**, and the controller
cannot force it to honor the structured results:

1. `collect()` hands the moderator the whole per-panelist result — raw panelist `content`,
   `claim_payload`, `claim_bindings`, `claim_verification`, **and** `boundary_decision` — with
   no deterministic step that rebuilds the answer from only admitted claims.
2. After a B1b repair, the original (malformed) prose is retained while the bound claims come
   from the repaired reply (`claim_payload_source = "repair"`); a naive renderer can mis-pair
   prose with bindings.
3. `representation_kind` / `rendering_mode` on a claim are **producer self-declared** and only
   enum-checked; the curated seed metadata is not yet authoritative and mismatches are not
   detected — so a panelist could present a `generated-rendering` as a `published-translation`.
4. The manifest's `mode_assurance` still frames hybrid B3 as full "runtime-enforced /
   fail-closed", and `user_visible_assurance` is `planned` — both now understate/overstate the
   true state.

Therefore today's real guarantee is a **controller-side structured-claim fail-closed boundary**,
**not** an end-to-end one. The renderer is a new trust boundary; per this project's
architecture-of-record discipline we fix its contract before implementing it.

## Decision

### 1. The renderer is a trust boundary; authority ≠ content

The finalizer's job is to control **what level of authority content may obtain**, not to
suppress all prose. A literal "rebuild only from admitted structured claims" would erase the
panelists' analysis, interpretation, rebuttal, and reasoning, leaving a bare verified-citation
list. Instead, output has three channels:

- **Textual authority channel (Surface A).** The only channel that may produce source-text
  presentation: quotations, attributions, provenance, span-backed factual assertions, and the
  published-translation / generated-rendering markers. Content here must trace to an admitted,
  verified, boundary-passed structured claim with an allowed `render_as`.
- **Interpretation channel (Surface B).** Carries panelist analysis, inference, theological
  interpretation, comparison, rebuttal, cross-tradition views, and reasoning over admitted
  evidence. It is rich but carries **no** `[Text]` authority and must never masquerade as source
  text or add new attribution/provenance/quotation/evidence status.
- **Audit / rejection channel.** Rejected claim ids, reason codes, missing evidence, metadata
  conflicts. It is **not** re-injected into ordinary answer synthesis.

### 2. Authority is defined by provenance and render path, not by semantic classification

Deciding, per sentence of free prose, whether it "constitutes a quotation / attribution" is
itself a semantic-classification trust boundary (unreliable across languages and paraphrase).
We do **not** do that. Authority is a property of **where content came from and which render
path produced it**:

- Surface A is produced **only** from admitted structured claims.
- All free prose lands in Surface B, which is rendered with a standing, non-removable
  non-authoritative frame.

A hidden "this verse states X" written into prose therefore needs no detection: it can only
appear in Surface B (framed non-authoritative), and there is no path for it to enter Surface A,
which is built from structured claims.

### 3. Surface A is built deterministically; the LLM does not free-write authority

Even seeing only admitted claims, an LLM left to free-write Surface A could rewrite a claim's
meaning, splice two claims, add an attribution that does not exist, present a meaning-rendering
as a published translation, or produce text that looks traceable but exceeds the source span.
So:

- **Surface A is serialized by code from admitted claims:** quotation text is taken verbatim
  from the canonical claim / evidence text; attribution is a deterministic template; provenance
  is filled from claim metadata; the rendering marker is policy-derived; `render_as` controls
  the allowed surface form. The LLM may only choose **which** admitted claims to present, their
  **order**, and **which thematic section** they sit in — never the authoritative wording.
- **Surface B is LLM-synthesized**, but the deterministic serializer adds a label the moderator
  cannot omit or rewrite (e.g. *"Council interpretation — not source text"*).

### 4. Structured render IR

The finalizer emits a structured intermediate representation; the deterministic serializer turns
it into Surface A + Surface B. `based_on_claim_ids` records an interpretation's argument
background only — it does **not** confer authority.

```json
{
  "authority_surface": [
    { "claim_id": "claim-001", "render_as": "quotation",
      "text": "...", "representation_kind": "published-translation",
      "rendering_marker": null }
  ],
  "interpretation_surface": [
    { "speaker_id": "council-01", "content": "...", "based_on_claim_ids": ["claim-001"] }
  ],
  "audit_summary": {
    "rejected_claim_ids": ["claim-002"],
    "reason_codes": ["verification-artifact-missing"]
  }
}
```

Two render inputs follow from this: `answer_render_input` (authority + interpretation surfaces +
permitted provenance/assurance metadata) and `audit_render_input` (rejected ids, reason codes,
verification/boundary diagnostics). The ordinary answer renderer sees **only** the first.

### 5. Post-render trace validation operates on render units, not on prose

The trace check is deterministic because it validates **render units**, not natural language.
Every authority-bearing render unit must pass, before serialization: `claim_id` exists; the
claim is admitted; `render_as` is allowed; `text` equals the admitted canonical quotation /
approved rendering; `representation_kind` / `rendering_mode` match the system-authoritative
metadata; any required rendering marker is present; the rights gate passes; the claim is actually
in the canonical authority view. Any untraceable, disallowed, or mismatched authority unit fails
finalization. This — not "scan the output text" — is the true `renderer-bypass`:

```text
authority unit references a denied claim          -> renderer-bypass
authority unit has no claim_id                    -> renderer-bypass
published-translation contradicts curated metadata-> renderer-bypass
quotation text differs from admitted canonical span-> renderer-bypass
required generated-rendering marker missing       -> renderer-bypass
```

### 6. Invariants (normative)

1. **Traceable authority.** No user-visible textual authority may exist unless represented by an
   authority-bearing render unit traceable to an admitted structured claim.
2. **Provenance-defined authority.** Authority is a property of provenance and render path, not a
   result of semantic classification. Only admitted structured claims may enter the authority
   surface.
3. **Deterministic trace validation.** Every authority-bearing render unit must pass deterministic
   claim / representation / rights / text / marker / `render_as` validation before serialization;
   any mismatch fails finalization.
4. **Controlled interpretation flow.** Non-authoritative prose may interpret, compare, elaborate,
   or critique, but must not be represented as source text or verified textual evidence. This
   prohibition is **instruction-bounded** within Surface B; the **machine-enforced** guarantee is
   that such prose cannot enter Surface A.
5. **No retroactive authority after repair.** Repaired structured claims must never confer
   authority on unmatched or original prose; only the repaired canonical claim record may enter
   Surface A.
6. **Separated render contexts.** The ordinary answer renderer receives only the answer render
   input; rejected payloads stay outside it and are reachable only through explicitly authorized
   audit/debug paths.
7. **Non-removable surface framing.** Surface labels and assurance markers are produced by the
   deterministic serializer, not by the LLM, and cannot be omitted or rewritten by the moderator.

### 7. The honest residual limit

> Machine enforcement covers the **construction and traceability of the authority surface**, not
> the **semantic correctness of every word in the interpretation surface**.

Surface B prose remains the panelists' words, instruction-bounded and framed non-authoritative.
We state this plainly so "authority isolation" is never re-described as "all prose is verified".

### 8. Related runtime decisions (specified here, built at P1)

- **Representation cross-check = runtime enforcement of existing policy, not new policy.** It
  enforces `no-generated-as-published` at the claim layer: when curated evidence metadata exists
  it is **system-authoritative**; a panelist's declaration is used only for mismatch diagnostics;
  a producer may not present `generated-rendering` as `published-translation`; a representation
  mismatch on a quotation fails closed (or downgrades to non-supporting).
- **`strict` profile is a configuration invariant, not flag shorthand.** It requires structured
  claims + verification + boundary + deterministic finalization + representation cross-check +
  assurance rendering, and **fails at startup/configuration** if any component is missing —
  it never silently degrades to B0.
- **Denial-reason naming.** P1 introduced the real render-time `renderer-bypass` reasons as the
  `TRACE_*` codes in `render_types.py` (§5). The OLDER controller-level `renderer-bypass` boundary
  reason actually detects a missing `claim_verification` artifact; renaming it to
  `verification-artifact-missing` is a **deferred follow-up** (a reason-code string is potentially a
  public contract, so it warrants a deprecation window — see CHANGELOG), not done in P1.

## The three rejections stay distinct (ADR 0002 §5)

| Stage | Rejects | Mechanism |
|---|---|---|
| B1b | malformed payload | `schema_status` → repair/drop |
| B2 | inadmissible evidence on `[Text]` | `verification_state` → remove edge / downgrade |
| B3 (controller) | unknown type / unverified `[Text]` / missing verification / unsupported protocol | `boundary_decision` → default-deny |
| **B3 (renderer, this ADR)** | untraceable / mismatched **authority render unit** | finalization fails (true `renderer-bypass`) |

## Delivery split

- **P0 (landed):** this ADR; assurance-honesty manifest edits (`mode_assurance` hybrid wording;
  additive `assurance_layers`); `CHANGELOG.md`. No runtime behavior change.
- **P1 (landed):** `render_types.py` (token-guarded authority units) + `render_finalizer.py`
  (canonical authority-unit builder; deterministic Surface A serializer; Surface B framing;
  independent trace validator with the `TRACE_*` render-time `renderer-bypass` reasons;
  representation system-authoritative cross-check; atomic `finalize`; `validate_strict_profile`);
  controller `profile="strict"` (config invariant), the `debate_finalize` entry/tool, and the
  workflow invariant that a strict run is not `finalized` until `debate_finalize` succeeds.
  Deferred follow-up: renaming the older controller `renderer-bypass` reason (see §8).

The P1 success condition was **not** "the moderator complied" but the following, which is met by
the token-guarded builder + independent trace re-derivation + atomic finalization:

> Even if the moderator maliciously or mistakenly asks to cite a denied claim, no supported API or
> data path can serialize it into Surface A.

## Consequences

- The guarantee can now be stated honestly as: **end-to-end machine-enforced construction and
  traceability of the finalized textual-authority surface (via `debate_finalize`), with explicitly
  non-authoritative, instruction-bounded interpretation prose.**
- Scope discipline: this applies to finalized / `profile="strict"` responses. The default hybrid
  prose path (no `debate_finalize`) is unchanged and not machine-enforced — assurance surfaces
  must not be read as "all hybrid output is finalized".

## Non-goals

- No runtime finalizer / serializer / trace validator in P0 (that is P1).
- Does not change B1b–B3 behavior or make structured mode the default.
- Does not attempt to semantically verify free interpretation prose.
