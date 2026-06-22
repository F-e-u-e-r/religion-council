# ADR 0005 — Stable Occurrence Identity for Network / Dynamic Retrieval

- Status: Accepted
- Scope: how the B1a adapter mints an **occurrence id** (the per-occurrence binding key a
  claim edge points at), and when it must refuse rather than mint an unstable one. Resolves
  the occurrence-identity question [ADR 0003](0003-retrieval-evidence-adapter.md) §4.6 left
  open (that ADR governs *artifact* identity; this one governs *occurrence* identity).
- Owner stage: **B1**, as **A2/A3 readiness** (see [ADR 0002](0002-roadmap-stage-nomenclature.md)).

## Context

`retrieval_evidence_adapter.occurrence_id` is the binding key persisted on every
`ClaimEvidenceEdge` and in the origins log. The artifact id is a content hash (ADR 0003 §4)
and is already backend-independent. The *occurrence* id is not: the same bytes can occur at
different work/locator/source lines, so identity must not collapse to the artifact id, and it
must stay stable across retrieval orderings or persisted audit references silently rot.

Before this ADR the adapter had two regimes:

1. **corpus-stable** — when a record carries `source_file` + `source_line` (file-based A0/A1),
   the id is `sha256(artifact_id, work, locator, source_file, source_line)`: stable across
   queries, independent of retrieval rank.
2. **index-fallback** — without origin hints, the id folds in the envelope `record_index`, so a
   different ordering yields a different id.

A network or dynamically-ordered backend (A3) supplies no `source_file`/`source_line` and may
return results in a query- or relevance-dependent order. Under the old code it would land on
**index-fallback**, minting occurrence ids that change when the same evidence is returned in a
different position — breaking claim bindings, audit reproducibility, and span verification that
referenced a prior id. This must fail closed instead.

## Decision

### 1. Three named, versioned occurrence-identity schemes

The scheme that minted an id is recorded explicitly on each seed
(`EvidenceSeed.occurrence_id_scheme`) and in the origins log, so persisted references are
self-describing:

- `occ/v1-corpus-stable` — `source_file` + `source_line` present (file-based legacy). The
  documented fallback ADR 0003 §4.6 permits for file-based retrieval; **retained unchanged**.
- `occ/v1-network-stable` — order-INDEPENDENT, minted from the content hash plus a stable key:
  an explicit `record_key` if present, else the `(work, locator)` pair. Used for
  network/dynamic acquisition.
- `occ/v1-index-fallback` — keyed on `record_index`, retrieval-order scoped. A deliberate
  stop-gap; **never** used for network/dynamic acquisition.

### 2. Stable occurrence-identity inputs

A record can yield an order-independent id when it carries any of:

- file-based origin hints (`source_file` + `source_line`), or
- an explicit backend-stable `record_key`, or
- a non-empty `(work, locator)` pair.

The content hash (`artifact_id`) and the byte span are always available (the adapter
content-addresses `record.text`), so they are combined with the above rather than relied on
alone — identical bytes recur, so a hash by itself cannot identify an occurrence.

### 3. Fail closed for network/dynamic acquisition without stable inputs

```text
if acquisition_origin ∈ STABLE_IDENTITY_REQUIRED_ORIGINS
   and no stable occurrence-identity inputs are present:
       raise StableIdentityError   # before any persistence, before claim binding
```

`STABLE_IDENTITY_REQUIRED_ORIGINS = {runtime-captured}` today; new network origins are added to
that set as they land. The check runs in the adapter's preflight, so a rejected envelope leaves
the snapshot store and origins log untouched, and the failure happens before B1b claim binding.
`StableIdentityError` subclasses `SchemaRejection`, so the controller's existing fail-closed
envelope handling rejects the run at `start()`.

### 4. No silent migration of existing ids

The id **bytes** of `corpus-stable` and `index-fallback` are unchanged; `network-stable` is a
new scheme that no previously-persisted record used. File-based retrieval therefore keeps its
exact occurrence ids and existing audit references remain reproducible. Any future change to a
legacy scheme's bytes is a planned migration, never a silent edit.

### 5. Collision behavior

Different bytes hash to different `artifact_id`, so they cannot share an occurrence id even at
the same locator. Identical bytes at an identical `(work, locator)` (or identical `record_key`)
**collapse to one identity** — that is the correct semantics (it is the same occurrence), not a
collision bug. Different locators / record keys over the same bytes stay distinct.

## Consequences

- A3 network retrieval can be implemented without the risk of unstable, order-dependent
  evidence identities; the enforcement is armed now and exercised by tests via
  `acquisition_origin="runtime-captured"`.
- File-based retrieval is unaffected (same scheme, same id bytes, same tests).
- A2 edition-backed evidence fits cleanly: an edition/snapshot identity or canonical record key
  is exactly a `record_key`, already a first-class stable input.
- The acceptance criteria hold: same evidence → same id across orderings; different spans do not
  collide; network records without stable identity fail before claim binding; persisted audit
  references remain reproducible (scoped as below).

## Known limitations

- **`occ/v1-corpus-stable` ids embed the absolute `source_file` path.** The retriever sets
  `source_file = str(Path(__file__).resolve()... )`, so a legacy corpus-stable id is reproducible
  **within one checkout/path**, not across relocated or re-cloned working copies — moving an
  otherwise-identical checkout changes those ids. (Relatedly, the two distribution copies —
  `skills/` and `.claude/skills/` — already mint different corpus-stable ids for the same excerpt,
  because their absolute paths differ.) This is the documented file-based legacy and is preserved
  intentionally: rewriting it would be exactly the silent id migration this ADR forbids. The
  cross-run reproducibility guarantee above is therefore **same-checkout** scoped for the
  corpus-stable scheme. The `network-stable` scheme has no such dependency (it keys on content
  hash + `record_key`/`work`+`locator`, never a path).
- A future **`occ/v2`** would replace the absolute path with a stable relative source key (or drop
  it in favor of a content/`record_key` identity) to make corpus-stable ids portable across clones.
  Because that changes persisted id bytes, it requires an explicit, planned migration (new scheme
  tag + dual-read/backfill), never a silent edit.

## Non-goals

- No network-retrieval backend is implemented here (deferred to A2/A3 behind their own
  benchmark/ADR). This ADR fixes the identity contract so that work cannot introduce unstable
  ids later.
- No change to artifact identity (ADR 0003 §4) and no migration of existing snapshots.
