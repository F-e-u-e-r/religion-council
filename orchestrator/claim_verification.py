"""B2 claim-level evidence validation against the curated-snapshot tier.

Takes B1b's bound claims (initial ``unverified``) plus a reader over the immutable snapshot
store and produces a SEPARATE verified result — it never mutates the B1b ``claim_bindings``
(whose initial VerificationResult is ``unverified`` by ADR 0003 §3). For each ``[Text]``
claim:

* each supporting edge is checked against the snapshot it points to and gains
  ``runtime-validated`` or ``failed``;
* a failed support edge is REMOVED from the claim (retained in ``removed_edges`` for audit);
* a ``[Text]`` claim that loses all support is downgraded to a non-supporting
  ``unverified-citation`` (policy ``failed-text-not-auto-interpretation``) — never relabeled
  ``[Interpretation]``;
* the council continues. This is claim-level validation, NOT B3 boundary fail-closed.

Span verification is the **curated-snapshot tier** (ADR 0003 §5): a verbatim byte match
against the snapshot the project ingested. It proves fidelity to *our snapshot*, not to a
published edition (``edition-backed-span-verified`` is A2). Per the policy compatibility
matrix only ``quotation`` edges require span verification; ``source-bound-summary`` requires
only a resolved evidence-edge (which B1b established), so it validates WITHOUT a span tier —
B2 never verbatim-matches a paraphrase.
"""
import policy_enums
from evidence_snapshot import canonical_bytes

CURATED_SNAPSHOT_TIER = "curated-snapshot-span-verified"
# Fail fast if the manifest enum drifts away from the tier this module emits.
assert CURATED_SNAPSHOT_TIER in policy_enums.SPAN_ASSURANCE_TIERS


def _find_span(snapshot_bytes, claim_text):
    """Byte span of ``claim_text`` within the canonical snapshot bytes, or None.

    The needle is canonicalized the same way the snapshot was (NFC + LF), so the match is
    deterministic across backends (ADR 0003 §4). The span is a byte offset + length over the
    snapshot bytes.
    """
    needle = canonical_bytes(claim_text)
    index = snapshot_bytes.find(needle)
    if index < 0:
        return None
    return {"byte_offset": index, "byte_length": len(needle)}


def _verify_edge(edge, claim_text, read_snapshot):
    """Verify one edge against its snapshot. Returns ``(state, tier, span, detail)``."""
    try:
        snapshot = read_snapshot(edge["artifact_id"])
    except Exception as exc:  # missing/corrupt snapshot -> the edge cannot be validated
        return "failed", None, None, "snapshot unreadable: {}".format(exc)
    if edge.get("evidence_type") == "quotation":
        span = _find_span(snapshot, claim_text)
        if span is None:
            return "failed", None, None, "quotation not found verbatim in curated snapshot"
        return "runtime-validated", CURATED_SNAPSHOT_TIER, span, None
    # source-bound-summary: the policy requires only a resolved evidence-edge, which exists and
    # is readable; a paraphrase is not verbatim-matched, so it validates without a span tier.
    return "runtime-validated", None, None, "evidence-edge (paraphrase; no span verification)"


def verify_bound_claims(bound_state, read_snapshot):
    """Verify a B1b ``BoundClaims`` state dict; return a verified state dict (additive).

    ``read_snapshot(artifact_id) -> bytes`` reads the canonical snapshot bytes (raises on a
    missing snapshot). The input is left unmutated.
    """
    verified = []
    for claim in bound_state.get("claims", []):
        # B2 validates [Text] claims only (policy text-requires-admissible-evidence).
        # [Interpretation] and producer-emitted unverified-citation carry forward UNCHANGED —
        # their edges (if any) are never verified or removed by B2.
        if claim.get("claim_type") != "text":
            verified.append(dict(claim))
            continue

        claim_text = claim.get("text", "")
        kept = []
        removed = []
        best_tier = None
        for edge in claim.get("edges", []):
            state, tier, span, detail = _verify_edge(edge, claim_text, read_snapshot)
            verified_edge = dict(edge)
            verified_edge["verification_state"] = state
            if span is not None:
                verified_edge["span"] = span
            if tier is not None:
                verified_edge["span_assurance_tier"] = tier
            if detail is not None:
                verified_edge["verification_detail"] = detail
            if state == "runtime-validated":
                kept.append(verified_edge)
                if tier == CURATED_SNAPSHOT_TIER:
                    best_tier = CURATED_SNAPSHOT_TIER
            else:
                removed.append(verified_edge)

        verified_claim = dict(claim)
        verified_claim["edges"] = kept
        if removed:
            verified_claim["removed_edges"] = removed
        if kept:
            verified_claim["verification_state"] = "runtime-validated"
            if best_tier is not None:
                verified_claim["span_assurance_tier"] = best_tier
        else:
            # All support failed: downgrade to a non-supporting unverified-citation
            # (policy failed-text-not-auto-interpretation). Never relabel [Interpretation].
            verified_claim["verification_state"] = "failed"
            verified_claim["claim_type"] = "unverified-citation"
            verified_claim["downgraded_from"] = "text"
        verified.append(verified_claim)

    return {"protocol_version": bound_state.get("protocol_version"), "claims": verified}


def verification_summary(verified_state):
    """Compact per-result counts for a moderator: validated / failed / downgraded claims."""
    claims = verified_state.get("claims", [])
    return {
        "claims": len(claims),
        "runtime_validated": sum(
            1 for c in claims if c.get("verification_state") == "runtime-validated"
        ),
        "failed": sum(1 for c in claims if c.get("verification_state") == "failed"),
        "downgraded": sum(1 for c in claims if c.get("downgraded_from") == "text"),
    }
