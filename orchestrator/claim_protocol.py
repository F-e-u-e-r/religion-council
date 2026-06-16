"""DRAFT structured claim protocol schema — dormant validator library (B1a).

WARNING — DRAFT: the shape is NOT frozen. B1a ships this only as a library
exercised by unit tests; no prompt emits it and no controller path invokes it, so
runtime schema rejection is not yet live (that is B1b). The version string is
therefore ``religion-council/claim/v1-draft``; the frozen ``v1`` is finalized at
B1b, once the artifact/seed *binding* shape is settled.

Scope today is schema-level only (ADR 0002 B1 / ADR 0003): it checks structure and
enum membership and never verifies evidence or decides admissibility; a B1
verification_state is always ``unverified``.

NOT validated here (deferred to B1b ``claim_binding``): the payload has no
``artifacts`` / ``evidence_seeds`` section, and an edge's ``artifact_id`` is only
checked to be a non-empty string — it is NOT resolved against an existing
Artifact / Span / occurrence. Dangling-reference validation lands at B1b.

Note: ``representation_kind`` has no ``unknown`` member in the policy, so a payload
that sets it to ``"unknown"`` is rejected here; omit the field instead.
"""
import policy_enums

DRAFT_PROTOCOL_VERSION = "religion-council/claim/v1-draft"


class SchemaRejection(ValueError):
    """A structured payload violated the schema (a retry / repair candidate)."""


def _require(condition, message):
    if not condition:
        raise SchemaRejection(message)


def _check_enum(value, allowed, field):
    _require(value in allowed, "{} not in enum: {!r}".format(field, value))


def validate_claim_payload_draft(payload):
    """Schema-only validation of a DRAFT ``religion-council/claim/v1-draft`` payload.

    Returns the payload unchanged on success; raises :class:`SchemaRejection`
    otherwise. Does not verify evidence, set verification, decide admissibility, or
    resolve an edge's artifact reference against a real Artifact/Span (B1b binding).
    """
    _require(isinstance(payload, dict), "payload must be an object")
    _require(
        payload.get("protocol_version") == DRAFT_PROTOCOL_VERSION,
        "unsupported protocol_version: {!r}".format(payload.get("protocol_version")),
    )

    claims = payload.get("claims")
    edges = payload.get("edges", [])
    _require(isinstance(claims, list) and claims, "claims must be a non-empty list")
    _require(isinstance(edges, list), "edges must be a list")

    claim_ids = set()
    for claim in claims:
        _require(isinstance(claim, dict), "each claim must be an object")
        cid = claim.get("claim_id")
        _require(isinstance(cid, str) and cid, "claim_id must be a non-empty string")
        _require(cid not in claim_ids, "duplicate claim_id: {!r}".format(cid))
        claim_ids.add(cid)
        _check_enum(claim.get("claim_type"), policy_enums.CLAIM_TYPES, "claim_type")
        _require(
            isinstance(claim.get("text"), str) and claim["text"] != "",
            "claim.text must be a non-empty string",
        )
        # Optional presentation dimensions; enum-checked only when present.
        # representation_kinds has no "unknown", so "unknown" is rejected here.
        rep = claim.get("representation_kind")
        if rep is not None:
            _check_enum(rep, policy_enums.REPRESENTATION_KINDS, "representation_kind")
        mode = claim.get("rendering_mode")
        if mode is not None:
            _check_enum(mode, policy_enums.RENDERING_MODES, "rendering_mode")

    for edge in edges:
        _require(isinstance(edge, dict), "each edge must be an object")
        _require(
            edge.get("claim_id") in claim_ids,
            "edge references unknown claim_id: {!r}".format(edge.get("claim_id")),
        )
        # artifact_id is only shape-checked here; resolving it to a real
        # Artifact / Span / occurrence is B1b binding, not B1a.
        _require(
            isinstance(edge.get("artifact_id"), str) and edge["artifact_id"],
            "edge.artifact_id must be a non-empty string",
        )
        _check_enum(edge.get("evidentiary_role"), policy_enums.EVIDENTIARY_ROLES, "evidentiary_role")
        _check_enum(edge.get("evidence_type"), policy_enums.EVIDENCE_TYPES, "evidence_type")
        _check_enum(edge.get("source_assurance"), policy_enums.SOURCE_ASSURANCES, "source_assurance")
        _check_enum(edge.get("verification_state"), policy_enums.VERIFICATION_STATES, "verification_state")

    return payload
