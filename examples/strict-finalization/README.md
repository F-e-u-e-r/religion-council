# Strict finalization walkthrough

This offline, standard-library-only example exercises the public controller lifecycle:

```text
debate_start(profile="strict", evidence_envelope=…)
→ debate_collect
→ finalization_required=true / finalized=false
→ debate_finalize
→ finalized=true
```

Run it from the repository root:

```bash
python3 examples/strict-finalization/run_example.py
```

The fixture replaces only the live Codex MCP transport; the real controller, evidence adapter,
claim binder, validator, fail-closed boundary, canonical authority builder, trace validator, and
serializer run unchanged. It needs neither network access nor a Codex login.

`evidence-envelope.json` is a one-record `religion-council/retrieval/v1` input with curated
representation metadata. The accepted fixture response has one structured text claim and one
interpretation claim. A second fixture response omits the structured payload, so the fail-closed
boundary produces a response-level denial.

The runner asserts that:

- strict mode sets `finalization_required=true` and stays `finalized=false` through collection;
- quotation text is read from the canonical snapshot span and authority carries the admitted claim
  ID;
- representation metadata is derived from the evidence catalog, not producer text;
- the denied payload never enters answer render input and yields an empty Surface A;
- Surface B framing is present for both the admitted and denied results;
- a malformed extra admitted claim causes an atomic trace failure with no partial Surface A; and
- the normalized output equals `expected-authority-surface.json`, so it is deterministic.

The example is run by the CI Python matrix. README and installation guidance link here for the
live Codex/Claude prerequisites and strict invocation.
