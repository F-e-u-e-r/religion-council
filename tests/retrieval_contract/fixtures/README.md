# Retrieval-contract fixtures (ADR 0006 §5)

Each subdirectory holds one `envelope.json` — a `religion-council/retrieval/v1` retrieval
envelope — exercising one clause of the shared contract. The fixtures are **retriever-independent**:
they are fed through the real B1 adapter (`orchestrator/retrieval_evidence_adapter.py`) +
`EvidenceStore`, the downstream both the portable and project retrievers share, so the same identity
semantics are asserted regardless of which backend produced an equivalent envelope. The
retriever-level half of the suite (shape / normalization / capabilities / stdlib-only) runs against
each retriever's *live* envelope instead.

| Fixture | What it pins | Acquisition used |
|---|---|---|
| `basic_corpus` | A well-formed, fully-conforming envelope: required fields present, canonical text, two distinct file-based occurrences; ids deterministic across runs. | `bundled` → `occ/v1-corpus-stable` |
| `duplicate_text` | Identical bytes at **different** locators stay **distinct** occurrences (no collapse); identical bytes at the **same** stable inputs **do** collapse to one occurrence (ADR 0005 §5). One artifact, two occurrences. | `bundled` → `occ/v1-corpus-stable` |
| `unicode_normalization` | Records that differ **only** by NFC/NFD or CRLF/LF normalize to one canonical artifact (and one occurrence). Identity is normalization-stable. Note: this fixture is intentionally **non-canonical** input — it tests the adapter's defensive normalization, not retriever output. | `bundled` |
| `missing_metadata` | Optional curation (provenance / rights / representation) absent → the envelope is still valid and binds; the resulting seeds carry no provenance/rights. | `bundled` |
| `dynamic_identity_required` | Underspecified **dynamic** records (no `work`/`locator`, no `source_file`/`source_line`, no `record_key`) **fail closed** under network acquisition rather than mint an order-scoped id — nothing is persisted (ADR 0005 §3). | `runtime-captured` → `StableIdentityError` |
| `no_result` | An empty record set is a valid envelope; the adapter yields zero seeds without error. | `bundled` |

`dynamic_identity_required` is deliberately **not** fully contract-conforming at the record level
(it omits `work`/`locator`, which are both required contract fields *and* stable-identity inputs):
that is exactly the degenerate dynamic result the system must refuse, so the suite does not run the
"envelope conforms" assertion on it.
