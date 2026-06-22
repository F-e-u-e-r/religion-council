# ADR 0006 — Retriever Fork and Shared Retrieval-Contract Conformance

- Status: Accepted
- Implementation: Implemented — migration phases 1–4 below have landed (the contract suite, the
  project retriever, and the retirement of byte-parity as the cross-implementation gate); phase 5
  (the retrieval benchmark) is deferred to a separate ADR. This ADR is the contract of record.
- Scope: replaces the **byte-identical `retrieve.py`** invariant with a **shared retrieval-envelope
  contract** and a conformance suite that both a *portable* and a *project* retriever must pass.
  Fixes identity (ADR [0005](0005-stable-occurrence-identity.md)) and artifact lifecycle
  (ADR [0003](0003-retrieval-evidence-adapter.md)) as the things a backend may **not** weaken.
- Owner stage: **A2 readiness** (the retrieval fork that ADR [0002](0002-roadmap-stage-nomenclature.md)
  §1 names: "A2 forks them and replaces parity with a shared contract-conformance suite"). It selects
  **no** backend — that is gated on a later benchmark ADR.

## Context

`v0.11.0` established stable occurrence identity (ADR 0005) and documented the limits of the
legacy path-bound id (`occ/v1-corpus-stable` embeds an absolute `source_file`). The retrieval seam
is still a single file kept in two byte-identical copies:

```text
skills/religion-council/scripts/retrieve.py
.claude/skills/religion-council/scripts/retrieve.py
must remain byte-identical          ← the A0–A1 invariant being retired here
```

Byte-parity was the right guarantee while there was exactly one implementation. It stops being
right the moment the project copy is allowed to grow a local index, a chunk store, or a RAG client:
two files that *must differ internally* cannot be guaranteed equal byte-for-byte. The roadmap
(ADR 0002 §1, A2/A3) and the parity test's own comment already anticipate the swap:

```text
new invariant:
portable retriever and project retriever may differ internally,
but both must pass the same retrieval contract-conformance suite.
```

Without this ADR, adding an index or RAG backend would risk coupling the B-axis enforcement
guarantees (B1 adapter, B2 verifier, B3 boundary, P1 finalizer) to backend-specific behavior. The
contract has to be written down — and proven by tests against more than one implementation —
**before** a second implementation exists, or the second implementation silently becomes the
contract.

## Decision

### 1. Fork the retrievers intentionally

There are two named retrievers with different obligations:

| | Portable retriever | Project retriever |
|---|---|---|
| **Lives in** | `skills/religion-council/scripts/retrieve.py` and its `.claude/skills/…` mirror | `orchestrator/project_retrieve.py` |
| **Dependencies** | Python **standard library only** | project modules allowed |
| **Backend** | file-based corpus parse + deterministic lexical rank | file-based **today**; may later use a local index / chunk store / RAG client |
| **Audience** | Codex / arbitrary agents / `skills/` install — no project checkout | the orchestrated council and its enforcement pipeline |
| **Guarantee** | conformance **and** byte-parity *between its own two copies* | conformance |

The two **portable copies** stay byte-identical to **each other** (they are the same artifact shipped
to two install locations). What is retired is the cross-implementation parity between the portable
retriever and the project retriever: those two may diverge internally and are bound only by the
contract.

### 2. The shared contract is the existing retrieval envelope (frozen version)

Both retrievers MUST emit the **retrieval envelope** already defined by ADR 0003 §1 and consumed by
`RetrievalEvidenceAdapterV1`:

```json
{ "contract_version": "religion-council/retrieval/v1", "records": [ … ] }
```

`contract_version` is **`religion-council/retrieval/v1`, unchanged.** It is load-bearing: it is the
adapter's `ACCEPTED_CONTRACT_VERSION`, so renaming it (e.g. to an illustrative
`retrieval-envelope/v1`) would break B1 negotiation for zero benefit. Shape negotiation trusts only
this string; each record's `version` field remains the *source edition* (e.g. `通行本`), not the API
contract.

**The envelope is what the retriever owns. Evidence identity is what the adapter mints — and the two
must not be conflated.** This is the load-bearing distinction in this ADR:

| Layer | Fields | Produced by | Backend-independent because |
|---|---|---|---|
| **Retrieval envelope** (contract surface) | `text`, `tradition`, `school`, `work`, `locator`, `language`, `version`, `category`, `label`, `evidence_type`, `verbatim`, `topic`; carried A1 curation `representation_kind` / `rendering_mode` / `provenance` / `rights`; **stable-identity inputs** `source_file`+`source_line` *or* `record_key` *or* the `(work, locator)` pair | the **retriever** | the retriever guarantees the field semantics |
| **Evidence identity & assurance** | `artifact_id`, byte `span` (`byte_offset`+`byte_length`), `occurrence_id`, `occurrence_id_scheme`, `acquisition_origin`, `source_assurance`, span-assurance tier | the **adapter** (`adapt()` + `EvidenceStore`), ADR 0003/0005 | content-addressing + the ADR 0005 schemes hash identically on every backend |

ADR 0006's field list (the plan's "Shared Retrieval Contract") spans both layers; this table is the
authoritative split. A retriever **does not mint `occurrence_id`** — it supplies the *inputs* from
which the adapter mints one, or it declares (capability metadata, §3) that it cannot, in which case
the adapter **fails closed** (§4.1). This keeps the contract honest under A3: `source_file` does not
exist for a network backend, but `record_key` or `(work, locator)` does, and the adapter mints
`occ/v1-network-stable` from those.

The required **record** fields a conforming envelope must carry are exactly today's contractual
fields (`docs/CORPUS.md` "Retrieval field contract"): `text`, `tradition`, `school`, `work`,
`locator`, `language`, `version`, `category`, `label`. `evidence_type` / `verbatim` / `topic` and the
A1 curation fields are additive-but-stable. `text` MUST already be canonical-normalizable: the
adapter content-addresses `UTF-8(NFC(text-with-LF-newlines))`, so a record whose `text` round-trips
through that normalization unchanged is required (the retriever must not emit, say, NFD text that the
snapshot store would silently fold).

### 3. Explicit backend capability reporting

Each retriever exposes a `capabilities()` block (and the equivalent `--capabilities` CLI flag for the
portable copy) so a caller can reason about a backend **without importing it**:

```json
{
  "retriever_kind": "portable-file" | "project-file" | "project-index" | "project-service",
  "contract_version": "religion-council/retrieval/v1",
  "supports_stable_occurrence_identity": true,
  "supports_network_acquisition": false
}
```

Invariants on the block:

- `contract_version` MUST equal the envelope's `contract_version`.
- **`supports_network_acquisition` ⇒ `supports_stable_occurrence_identity`.** A backend that acquires
  bytes dynamically cannot also disclaim stable identity — that is precisely the ADR 0005 fail-closed
  condition, surfaced as a *declared capability* so it is checkable before a single record is
  retrieved. A retriever that cannot guarantee stable identity MUST report
  `supports_network_acquisition: false`.

The block is additive metadata, **not** part of `contract_version`: adding a `retriever_kind` value
or a new capability key does not bump the envelope version.

### 4. Required invariants

#### 4.1 Stable evidence identity (no order-scoped ids)

No dynamic, networked, indexed, or reorderable retriever may cause the adapter to mint an
order-scoped (`occ/v1-index-fallback`) occurrence id. The enforcement already exists (ADR 0005): for
a `STABLE_IDENTITY_REQUIRED_ORIGINS` acquisition the adapter raises `StableIdentityError` — before
any persistence, before claim binding — when stable inputs are absent. This ADR adds the *retriever
side* of that contract: such a retriever MUST supply stable inputs and report
`supports_stable_occurrence_identity: true`. Missing inputs fail closed; they are never papered over
with a list position.

#### 4.2 Same envelope semantics

The same query against equivalent corpus data MUST produce **semantically equivalent** envelopes
across retrievers, even if ranking internals or record ordering differ. "Semantically equivalent"
means: same record-field semantics, same normalization, and — fed through the adapter — the same
`artifact_id` and the same stable `occurrence_id` for the same occurrence. Ranking *order* is **not**
part of the contract except where §4.6 requires determinism.

#### 4.3 No provenance weakening

A richer backend MUST NOT drop `provenance`, `rights`, `representation_kind` / `rendering_mode`, or
the assurance inputs just because it has more data. Carried-not-trusted metadata (ADR 0003 §2) is
carried by **every** conforming retriever when the curation marks a record.

#### 4.4 No portable dependency creep

The portable retriever MUST import standard-library modules only — no project imports, no
third-party packages, no network, no index dependency. This is what keeps it usable from `skills/`
by an arbitrary agent with no project checkout. It is enforced by an import-introspection test, not
just by convention.

#### 4.5 B-axis compatibility

B1 adapter, B2 verifier, B3 boundary, and P1 finalizer consume the **envelope** (and the adapter's
output), never a retriever implementation. None of them may grow backend-specific branches. If a new
backend needs new downstream behavior, that is a new envelope field (additive) or a new contract
version (§7) — not an `if project_index:` in an enforcement module.

#### 4.6 Deterministic output where required

For a fixed `(corpus, query, k)` a single retriever MUST return a deterministic envelope (stable
record set and stable ordering). Determinism *across* retrievers is required for identity (§4.2) but
**not** for ranking order — a future ranker may legitimately order differently.

### 5. The contract-conformance suite

A single shared fixture + assertion suite is run against **both** retrievers:

```text
tests/retrieval_contract/
├── fixtures/
│   ├── basic_corpus/                # well-formed envelope; required fields, ordering, no-collapse
│   ├── duplicate_text/              # identical text at different locators → distinct occurrences
│   ├── unicode_normalization/       # NFC + LF folding is consistent and identity-stable
│   ├── missing_metadata/            # optional metadata absent → still valid; present → preserved
│   ├── dynamic_identity_required/   # dynamic acquisition without stable inputs → fail closed
│   └── no_result/                   # empty record set is a valid envelope
├── contract_assertions.py           # the shared battery (imported by both test modules)
├── test_contract_portable.py        # battery vs the portable retriever
└── test_contract_project.py         # battery vs the project retriever
```

The battery has two halves, matching the §2 layer split:

- **Retriever-level** (run against each retriever's *live* envelope over the real curated corpus):
  envelope is valid JSON-able; `contract_version` correct; required record fields present and typed;
  `text` is NFC/LF-canonical; ordering deterministic; carried `provenance`/`rights` preserved when
  curated; `capabilities()` well-formed and obeys the network⇒stable invariant; **portable imports
  are stdlib-only**.
- **Identity-level** (run by feeding the shared fixture envelopes through the real adapter +
  `EvidenceStore`, the downstream both retrievers share): ids are deterministic across runs;
  duplicate text at distinct locators does **not** collapse to one occurrence; identical
  `(work, locator)` over identical bytes *does* collapse (correct, ADR 0005 §5); reorder-invariance
  for the network-stable scheme; dynamic acquisition without stable inputs raises
  `StableIdentityError` and persists nothing; the `no_result` envelope yields zero seeds without
  error.

Both test modules import the **same** `contract_assertions` functions, so "passes the suite" means
the identical battery — there is no portable-only or project-only assertion except the stdlib-import
check (which is meaningful only for the portable copy).

### 6. What stays forbidden until a benchmark / backend ADR

This ADR fixes the *contract*. It selects **no** backend. The following remain out of scope and must
not be implied by any wording, capability value, or assurance footer until a later benchmark ADR
provides evidence (see [non-goals](#non-goals)):

- vector-DB selection, embedding-model selection, chunking-strategy finalization;
- a network retrieval service, an API server, semantic-search ranking;
- **edition-backed** assurance claims (still A2; the curated-snapshot tier is the ceiling today);
- dropping the portable file-based retriever.

A `project-index` / `project-service` `retriever_kind` value is *reserved* in the enum so the contract
need not change when such a backend lands — reserving the name is not building the backend.

### 7. Versioning & compatibility

- The envelope version is **`religion-council/retrieval/v1`** and stays v1 through this work.
- **Additive** fields (new optional record keys, new capability keys, new `retriever_kind` values) do
  **not** bump the version; existing consumers ignore unknown keys.
- A **breaking** change (renaming/removing a required field, changing `text` canonicalization) mints
  **`…/retrieval/v2`**; the adapter then negotiates (accept v1 and v2, or dual-read) — never a silent
  reinterpretation of v1. This mirrors the ADR 0005 "no silent migration" rule for identity bytes.
- Capability metadata is versioned *with* the envelope (its `contract_version` field) but is
  otherwise additive.

## Migration: byte-parity → contract-conformance

The swap is staged so each step is independently green. **Status: phases 1–4 are implemented; phase
5 is deferred to a separate benchmark ADR.**

1. **ADR only** *(this document)* — no runtime change.
2. **Contract fixtures + suite** — add `tests/retrieval_contract/`; the existing retriever passes
   unchanged; the two portable copies stay byte-identical.
3. **Project retriever entry point** — add `orchestrator/project_retrieve.py`, still file-based,
   wrapping the portable retriever and adding `capabilities()`; wire `test_contract_project.py`.
4. **Retire byte-parity as the hard cross-implementation invariant** — once both retrievers pass the
   shared suite, the cross-implementation byte-parity test is replaced by contract conformance. A
   **narrow** byte-parity check is *retained* only for the two intentionally-shared portable copies
   (`skills/` ↔ `.claude/skills/`), which remain the same artifact.
5. **Open benchmark work** *(separate ADR)* — only after the above does the project define
   `docs/benchmarks/retrieval-v1.md`, which decides whether lexical / local-index / hybrid / vector
   retrieval is justified. No backend is chosen here.

## Consequences

- The project retriever can later grow an index/RAG backend without touching B1/B2/B3/P1: it changes
  its `retriever_kind` and internals, the envelope and the conformance suite stay put.
- Stable occurrence identity (ADR 0005) is preserved under reorder, duplicate text, and backend
  change, because identity is minted by the adapter from envelope inputs the contract guarantees —
  not by the retriever and not from list position.
- The portable retriever stays install-free and usable by any agent; the stdlib-only rule is now
  test-enforced, not aspirational.
- Byte-parity stops being the *only* protection; it is demoted to a narrow same-artifact check while
  the contract suite becomes the cross-implementation guarantee.

## Acceptance criteria

This ADR answers, and the implementation satisfies, the questions A2 readiness raised:

- **What the two retrievers are** — portable (stdlib, file-based, dual-copy) and project
  (`orchestrator/project_retrieve.py`, may evolve), §1.
- **What contract they share** — the `religion-council/retrieval/v1` envelope + `capabilities()`, with
  identity minted downstream by the adapter, §2–§3.
- **What byte-parity is replaced with** — the shared contract-conformance suite; byte-parity is
  retained only for the two portable copies, §5–§6.
- **What stays stdlib-only** — the portable retriever, test-enforced, §4.4.
- **How stable occurrence identity is enforced** — ADR 0005 fail-closed + the retriever-side
  capability/stable-input obligation, §4.1.
- **What conformance tests are required** — the two-half battery in §5.
- **What cannot be built until benchmark evidence exists** — backend/RAG selection, edition-backed
  assurance, dropping the portable retriever, §6 + non-goals.

> After this ADR and its implementation, Religion Council has separate portable and project
> retrievers that may evolve independently while preserving one shared evidence-envelope contract,
> stable occurrence identity, and the same downstream citation-enforcement guarantees.

It still does **not** claim that RAG has been selected, that semantic retrieval beats lexical, that
edition-backed assurance is available, or that portable mode has the same runtime enforcement as
strict hybrid mode.

## Non-goals

- **No backend is selected or implemented** (no vector DB, embedding model, chunking finalization,
  network service, API server, or semantic ranking). Those are gated on the benchmark ADR (phase 5).
- **No new occurrence/artifact scheme** and no migration of existing ids or snapshots (ADR 0003/0005
  stand unchanged); this ADR only fixes which inputs the contract must carry.
- **No removal of the portable retriever** and no change to `contract_version`.
