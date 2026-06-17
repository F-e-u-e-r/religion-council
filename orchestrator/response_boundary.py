"""B3 response-boundary fail-closed gate.

The third and final rejection in the enforcement ladder (ADR 0002 §5) and the ONLY
fail-closed one. Where B1b repairs/drops a malformed payload and B2 removes a failed support
edge — both *continue* — B3 DEFAULT-DENIES at the response boundary, before the user-facing
renderer. A claim is admitted only if it affirmatively passes; anything unknown, unverified,
bypassing the pipeline, or on an unsupported protocol is denied by default.

It runs over a B2 verified response (``claim_verification``) and never re-verifies evidence or
re-checks schema — it is the boundary backstop, kept distinct from B1b schema-reject
(``schema_status``) and B2 verify-fail (``verification_state``). Within the hybrid controller
it produces the authoritative per-response decision over the structured claims; the moderator
must render only admitted claims (rendering anything else is itself the renderer-bypass that
this gate default-denies).
"""
import claim_protocol
import policy_enums

# Response-level deny reasons (deny the whole response):
RENDERER_BYPASS = "renderer-bypass"
UNSUPPORTED_PROTOCOL = "unsupported-protocol"
# Claim-level deny reasons:
UNKNOWN_CLAIM_TYPE = "unknown-claim-type"
UNSTRUCTURED_EVIDENCE_BYPASS = "unstructured-evidence-bypass"

# Fail fast if the manifest enum drifts from the reasons this gate emits.
assert {
    RENDERER_BYPASS,
    UNSUPPORTED_PROTOCOL,
    UNKNOWN_CLAIM_TYPE,
    UNSTRUCTURED_EVIDENCE_BYPASS,
} <= policy_enums.BOUNDARY_DENIAL_REASONS


def _deny_response(reason):
    return {
        "admitted": False,
        "response_denial": reason,
        "claims": [],
        "admitted_count": 0,
        "denied_count": 0,
    }


def _gate_claim(claim, known_claim_types):
    claim_id = claim.get("claim_id")
    claim_type = claim.get("claim_type")
    if claim_type not in known_claim_types:
        return {"claim_id": claim_id, "decision": "deny", "reason": UNKNOWN_CLAIM_TYPE}
    if claim_type == "text":
        if claim.get("verification_state") == "runtime-validated":
            return {"claim_id": claim_id, "decision": "admit", "render_as": "text"}
        # A [Text] reaching the boundary without runtime-validated evidence bypassed the
        # structured/verified pipeline -> default-deny (the fail-closed backstop; B2 normally
        # downgrades a failed [Text] to unverified-citation, so this catches the abnormal case).
        return {
            "claim_id": claim_id,
            "decision": "deny",
            "reason": UNSTRUCTURED_EVIDENCE_BYPASS,
        }
    if claim_type == "unverified-citation":
        # Honestly marked; retained as non-supporting (policy) — admit, but never as [Text].
        return {"claim_id": claim_id, "decision": "admit", "render_as": "non-supporting"}
    if claim_type == "interpretation":
        return {"claim_id": claim_id, "decision": "admit", "render_as": "interpretation"}
    # Fail-closed catch-all: a known enum value with no render rule is denied, not passed.
    return {"claim_id": claim_id, "decision": "deny", "reason": UNKNOWN_CLAIM_TYPE}


def gate_response(result, supported_protocol=None, known_claim_types=None):
    """Fail-closed boundary decision for one panelist result.

    Returns ``{admitted, response_denial, claims:[{claim_id, decision, reason|render_as}],
    admitted_count, denied_count}``. Default-deny: a missing verification (pipeline bypass) or
    an unsupported protocol denies the whole response; otherwise each claim is gated and only
    affirmatively-passing claims are admitted.
    """
    supported_protocol = supported_protocol or claim_protocol.PROTOCOL_VERSION
    known_claim_types = (
        known_claim_types if known_claim_types is not None else policy_enums.CLAIM_TYPES
    )

    verified = result.get("claim_verification")
    if not isinstance(verified, dict):
        return _deny_response(RENDERER_BYPASS)
    if verified.get("protocol_version") != supported_protocol:
        return _deny_response(UNSUPPORTED_PROTOCOL)

    decisions = [_gate_claim(claim, known_claim_types) for claim in verified.get("claims", [])]
    admitted_count = sum(1 for d in decisions if d["decision"] == "admit")
    return {
        "admitted": True,  # response-level checks passed; per-claim decisions filter rendering
        "response_denial": None,
        "claims": decisions,
        "admitted_count": admitted_count,
        "denied_count": len(decisions) - admitted_count,
    }
