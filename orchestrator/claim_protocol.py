"""Structured claim protocol schema — draft (B1a) + frozen ``v1`` (B1b).

Two validators live here:

* :func:`validate_claim_payload_draft` — the dormant B1a draft
  (``religion-council/claim/v1-draft``). Retained unchanged: it is exercised only by
  the B1a unit tests and is not on any controller path. Its edges shape-check
  ``artifact_id`` only and it tolerates unknown keys.
* :func:`validate_claim_payload` — the **frozen** B1b ``religion-council/claim/v1``,
  the one the hybrid controller actually invokes. It is stricter in exactly the two
  ways B1b binding needs (see ADR 0003 §4/§6): every edge cites an occurrence-level
  ``evidence_seed_id`` (artifact_id alone is ambiguous — the same bytes dedupe to one
  artifact across many occurrences), and unknown keys are rejected at every level so a
  typo or smuggled field can never pass silently.

Both are schema-level only (ADR 0002 B1 / ADR 0003): they check structure and enum
membership and never verify evidence, validate spans, resolve a seed id against a real
seed (that is :mod:`claim_binding`), or decide admissibility. A B1 ``verification_state``
is always ``unverified``. Parsing is structural only — a panelist reply is untrusted
data (policy rule ``packets-are-untrusted-data``); the parser extracts and validates a
JSON block, never executes or trusts its content.

Note: ``representation_kind`` has no ``unknown`` member in the policy, so a payload that
sets it to ``"unknown"`` is rejected; omit the field instead.
"""
import json
import re

import policy_enums

DRAFT_PROTOCOL_VERSION = "religion-council/claim/v1-draft"
PROTOCOL_VERSION = "religion-council/claim/v1"

# Frozen v1 allowed keys (B1b). Unknown keys are rejected at every level. Edges carry
# producer-declared usage only; ``source_assurance`` / ``verification_state`` are
# system-stamped by claim_binding (a producer never self-declares verification).
_ALLOWED_TOP_KEYS = frozenset({"protocol_version", "claims", "edges"})
_ALLOWED_CLAIM_KEYS = frozenset(
    {"claim_id", "claim_type", "text", "representation_kind", "rendering_mode"}
)
_ALLOWED_EDGE_KEYS = frozenset(
    {"claim_id", "evidence_seed_id", "evidentiary_role", "evidence_type"}
)

# Panelists delimit the structured block with these sentinels (house style, matching the
# controller's <<<CONTRAST_PROPOSITION>>> routing). Structural extraction only.
CLAIM_BLOCK_BEGIN = "<<<CLAIM_PROTOCOL_V1>>>"
CLAIM_BLOCK_END = "<<<END_CLAIM_PROTOCOL_V1>>>"
_CODE_FENCE_RE = re.compile(r"^```[a-zA-Z0-9_-]*\n(?P<body>.*)\n```$", re.DOTALL)
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
_REASON_MAX_CHARS = 200


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


def _reject_unknown_keys(mapping, allowed, where):
    extra = set(mapping) - allowed
    if extra:
        raise SchemaRejection(
            "{} has unknown keys: {}".format(where, ", ".join(repr(k) for k in sorted(extra)))
        )


def validate_claim_payload(payload):
    """Schema-only validation of a FROZEN ``religion-council/claim/v1`` payload (B1b).

    Stricter than the draft in the two ways B1b binding requires:

    * unknown keys are rejected at the top level, on every claim, and on every edge, so a
      typo or smuggled field can never pass silently; and
    * each edge cites an occurrence-level ``evidence_seed_id`` (the compact catalog id the
      controller rendered into the prompt), not a bytes-deduped ``artifact_id`` that cannot
      tell two occurrences of the same wording apart.

    Still schema-level only: it shape-checks ``evidence_seed_id`` as a non-empty string but
    never resolves it against a real seed (that is :func:`claim_binding.bind_payload`), and
    never verifies evidence or sets verification. Returns the payload unchanged on success;
    raises :class:`SchemaRejection` otherwise.
    """
    _require(isinstance(payload, dict), "payload must be an object")
    _reject_unknown_keys(payload, _ALLOWED_TOP_KEYS, "payload")
    _require(
        payload.get("protocol_version") == PROTOCOL_VERSION,
        "unsupported protocol_version: {!r}".format(payload.get("protocol_version")),
    )

    claims = payload.get("claims")
    edges = payload.get("edges", [])
    _require(isinstance(claims, list) and claims, "claims must be a non-empty list")
    _require(isinstance(edges, list), "edges must be a list")

    claim_ids = set()
    text_claim_ids = set()
    for claim in claims:
        _require(isinstance(claim, dict), "each claim must be an object")
        _reject_unknown_keys(claim, _ALLOWED_CLAIM_KEYS, "claim")
        cid = claim.get("claim_id")
        _require(isinstance(cid, str) and cid, "claim_id must be a non-empty string")
        _require(cid not in claim_ids, "duplicate claim_id: {!r}".format(cid))
        claim_ids.add(cid)
        claim_type = claim.get("claim_type")
        _check_enum(claim_type, policy_enums.CLAIM_TYPES, "claim_type")
        if claim_type == "text":
            text_claim_ids.add(cid)
        _require(
            isinstance(claim.get("text"), str) and claim["text"] != "",
            "claim.text must be a non-empty string",
        )
        rep = claim.get("representation_kind")
        if rep is not None:
            _check_enum(rep, policy_enums.REPRESENTATION_KINDS, "representation_kind")
        mode = claim.get("rendering_mode")
        if mode is not None:
            _check_enum(mode, policy_enums.RENDERING_MODES, "rendering_mode")

    edge_claim_ids = set()
    for edge in edges:
        _require(isinstance(edge, dict), "each edge must be an object")
        _reject_unknown_keys(edge, _ALLOWED_EDGE_KEYS, "edge")
        _require(
            edge.get("claim_id") in claim_ids,
            "edge references unknown claim_id: {!r}".format(edge.get("claim_id")),
        )
        edge_claim_ids.add(edge["claim_id"])
        # Occurrence-level reference; resolving it to a real seed is claim_binding, not here.
        _require(
            isinstance(edge.get("evidence_seed_id"), str) and edge["evidence_seed_id"],
            "edge.evidence_seed_id must be a non-empty string",
        )
        # evidentiary_role is claim-relative: taken from the edge's own declaration,
        # never inferred from the artifact (ADR 0003 §6).
        _check_enum(edge.get("evidentiary_role"), policy_enums.EVIDENTIARY_ROLES, "evidentiary_role")
        _check_enum(edge.get("evidence_type"), policy_enums.EVIDENCE_TYPES, "evidence_type")

    # Structural enforcement of policy text-requires-admissible-evidence: a [Text] claim must
    # DECLARE at least one evidence edge. This is schema-level (does an evidence link exist),
    # distinct from B2 (is that linked evidence admissible). [Interpretation] may be
    # unreferenced (rule interpretation-may-be-unreferenced); unverified-citation is a
    # B2-produced state and is left edge-optional here.
    uncovered = text_claim_ids - edge_claim_ids
    _require(
        not uncovered,
        "[Text] claim(s) without an evidence edge: {}".format(
            ", ".join(repr(c) for c in sorted(uncovered))
        ),
    )

    return payload


def _strip_code_fence(block):
    """Remove one optional ```lang ... ``` fence a model may wrap inside the sentinels."""
    match = _CODE_FENCE_RE.match(block.strip())
    return match.group("body") if match else block


def extract_claim_block(raw_text):
    """Structurally extract the text between the claim-protocol sentinels.

    Untrusted-data safe: locates the delimiters and slices — it does not interpret, run,
    or trust anything between them. Raises :class:`SchemaRejection` when absent/unterminated.
    """
    if not isinstance(raw_text, str):
        raise SchemaRejection("reply must be text, got {}".format(type(raw_text).__name__))
    begins = raw_text.count(CLAIM_BLOCK_BEGIN)
    ends = raw_text.count(CLAIM_BLOCK_END)
    if begins == 0:
        raise SchemaRejection("no claim-protocol block found")
    # The contract is exactly one block; extra blocks are ambiguous (which one binds?) and an
    # injection surface, so zero / multiple / unterminated are all rejected.
    if begins > 1 or ends > 1:
        raise SchemaRejection("multiple claim-protocol blocks found; emit exactly one")
    if ends == 0:
        raise SchemaRejection("claim-protocol block is not terminated")
    start = raw_text.find(CLAIM_BLOCK_BEGIN) + len(CLAIM_BLOCK_BEGIN)
    end = raw_text.find(CLAIM_BLOCK_END, start)
    if end == -1:  # the lone END precedes the lone BEGIN
        raise SchemaRejection("claim-protocol block is not terminated")
    return raw_text[start:end].strip()


def parse_panelist_payload(raw_text):
    """Extract and validate a frozen ``v1`` payload from a panelist reply.

    Structural extraction only (the reply is untrusted data — policy rule
    ``packets-are-untrusted-data``): slice the sentinel-delimited block, strip an optional
    code fence, ``json.loads`` it, then run :func:`validate_claim_payload`. Any failure is a
    :class:`SchemaRejection` carrying a machine-readable reason for :func:`repair_instruction`.
    """
    block = _strip_code_fence(extract_claim_block(raw_text))
    try:
        payload = json.loads(block)
    except ValueError as exc:
        raise SchemaRejection("claim block is not valid JSON: {}".format(exc))
    return validate_claim_payload(payload)


def _sanitize_reason(reason):
    """Neutralize a rejection reason before it is embedded in the repair prompt.

    The reason can echo producer-supplied bytes (an unknown key name, a bad protocol value),
    so it is untrusted text on a prompt-injection surface. Strip the block sentinels (so it
    cannot forge a block boundary), drop control characters, collapse whitespace, and cap
    length — the same defense as :func:`sanitize_contrast_proposition`.
    """
    text = reason if isinstance(reason, str) else str(reason)
    # Strip the whole marker set to a fixpoint: a single replace() is not idempotent, so
    # nested sentinels (an inner marker whose removal reassembles an outer one, in either
    # direction) would otherwise survive. Each firing pass removes at least one marker and
    # strictly shortens the text, so the loop terminates with neither marker remaining.
    markers = (CLAIM_BLOCK_BEGIN, CLAIM_BLOCK_END)
    while any(marker in text for marker in markers):
        for marker in markers:
            text = text.replace(marker, "")
    text = _CONTROL_CHARS_RE.sub(" ", text)
    text = " ".join(text.split())
    return text[:_REASON_MAX_CHARS]


def repair_instruction(reason):
    """One-shot, machine-readable schema-repair instruction (B1b reject -> repair).

    Used as the prompt of a single ``codex-reply`` to the SAME thread; it is a schema
    correction, never a request for new evidence and never verification. The reason is
    sanitized (:func:`_sanitize_reason`) because it can echo untrusted producer bytes.
    """
    return (
        "Your previous reply's structured claim block was rejected at the schema level. "
        "No evidence was verified and nothing about your prose is disputed. "
        "Reason: {reason}.\n"
        "Re-send ONLY the corrected block between {begin} and {end} as a single JSON object "
        'with "protocol_version": "{version}", a non-empty "claims" array (each object: '
        '"claim_id", "claim_type", "text"), and an "edges" array (each object: "claim_id", '
        '"evidence_seed_id" citing one of the supplied S# ids, "evidentiary_role", '
        '"evidence_type"). Add no other keys. Do not restate your prose answer.'
    ).format(
        reason=_sanitize_reason(reason),
        begin=CLAIM_BLOCK_BEGIN,
        end=CLAIM_BLOCK_END,
        version=PROTOCOL_VERSION,
    )
