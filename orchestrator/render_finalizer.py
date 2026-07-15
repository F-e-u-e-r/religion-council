"""Renderer finalizer (ADR 0004): canonical authority builder + trace validator + serializer.

Pipeline (deterministic; the LLM is not in it):

    verified claims + boundary decision + catalog + snapshot
        -> canonical authority units (Surface A) + interpretation units (Surface B) + audit
        -> independent trace validation (re-derive from source, compare)
        -> deterministic Surface A serialization

Guarantees (ADR 0004): authority is minted ONLY here from admitted, verified, boundary-passed
claims; quotation text is sourced from the snapshot span (never producer text); representation
is system-authoritative (a producer may self-downgrade to generated-rendering but never self-raise
to published-translation); finalization is ATOMIC — any bypass raises :class:`FinalizationError`
and no Surface A is produced.
"""
import policy_enums
from render_types import (  # noqa: F401  (re-exported reasons used by callers/tests)
    _AUTHORITY_MINT,
    ALLOWED_AUTHORITY_RENDER_AS,
    RENDER_AS_QUOTATION,
    RENDER_AS_SOURCE_BOUND_SUMMARY,
    TRACE_CLAIM_NOT_ADMITTED,
    TRACE_INTERPRETATION_ONLY,
    TRACE_MARKER_MISSING,
    TRACE_NOT_FROM_BUILDER,
    TRACE_RENDER_AS_DISALLOWED,
    TRACE_REPRESENTATION_MISMATCH,
    TRACE_RIGHTS_BLOCKED,
    TRACE_TEXT_NOT_CANONICAL,
    TRACE_UNKNOWN_CLAIM,
    AnswerRenderInput,
    AuditRenderInput,
    AuditSummary,
    AuthorityRenderUnit,
    FinalizationError,
    FinalizedResponse,
    InterpretationRenderUnit,
)

STRICT_REQUIREMENTS = ("structured_claims", "verify_claims", "fail_closed")


def validate_strict_profile(flags):
    """Config-time gate for ``profile="strict"`` (ADR 0004 §8). Fail-fast, never degrade.

    ``flags`` maps the structured-mode switches to booleans. Returns the normalized (all-True)
    flag dict; raises :class:`FinalizationError` listing any missing component. A missing piece is
    a configuration error — strict must never silently fall back to B0.
    """
    missing = [name for name in STRICT_REQUIREMENTS if not flags.get(name)]
    if missing:
        raise FinalizationError(
            "strict-config-incomplete", "missing required components: {}".format(", ".join(missing))
        )
    return {name: True for name in STRICT_REQUIREMENTS}


def _seed_for(edge, catalog):
    if catalog is None:
        return None
    return catalog.get(edge.get("evidence_seed_id"))


def _attribution(seed, edge):
    if seed is not None:
        parts = [part for part in (seed.work, seed.locator) if part]
        if parts:
            return " ".join(parts)
    return "(source: {})".format(edge.get("evidence_seed_id") or "unknown")


def _marker_for(representation_kind, rendering_mode):
    if representation_kind == "generated-rendering":
        return "generated-rendering"
    if rendering_mode == "meaning-rendering":
        return "meaning-rendering"
    return None


def _valid_optional_enum(value, allowed):
    return value is None or value in allowed


def _rights_ok(seed):
    """A1 presentation/provenance metadata must carry the curated per-snippet rights note."""
    if seed is None:
        return True
    has_curated_presentation = any(
        getattr(seed, name, None) is not None
        for name in ("representation_kind", "rendering_mode", "provenance")
    )
    if not has_curated_presentation:
        return True
    rights = getattr(seed, "rights", None)
    return isinstance(rights, str) and bool(rights.strip())


def _resolve_representation(claim, seed):
    """Return ``(representation_kind, marker, reason_or_None)``.

    System-authoritative (ADR 0004 §8): when the curated seed carries representation metadata it
    wins and a producer mismatch is a bypass. Without curated metadata, a producer may only
    self-DOWNGRADE (declare generated-rendering -> honored + marker); it may never self-RAISE
    (a producer-declared published-translation is dropped to a diagnostic, not granted).
    """
    system_rep = getattr(seed, "representation_kind", None) if seed is not None else None
    system_mode = getattr(seed, "rendering_mode", None) if seed is not None else None
    declared_rep = claim.get("representation_kind")
    declared_mode = claim.get("rendering_mode")
    if not _valid_optional_enum(system_rep, policy_enums.REPRESENTATION_KINDS):
        return None, None, TRACE_REPRESENTATION_MISMATCH
    if not _valid_optional_enum(system_mode, policy_enums.RENDERING_MODES):
        return None, None, TRACE_REPRESENTATION_MISMATCH
    if not _valid_optional_enum(declared_rep, policy_enums.REPRESENTATION_KINDS):
        return None, None, TRACE_REPRESENTATION_MISMATCH
    if not _valid_optional_enum(declared_mode, policy_enums.RENDERING_MODES):
        return None, None, TRACE_REPRESENTATION_MISMATCH
    if system_rep is not None:
        if declared_rep is not None and declared_rep != system_rep:
            return None, None, TRACE_REPRESENTATION_MISMATCH
        return system_rep, _marker_for(system_rep, system_mode), None
    if declared_rep == "generated-rendering":
        return "generated-rendering", "generated-rendering", None
    # published-translation / original-text / none, without system backing -> not granted.
    return None, None, None


def _canonical_quotation_text(edge, read_snapshot):
    """The quotation's bytes taken FROM the snapshot span, decoded — never the producer text."""
    span = edge.get("span")
    artifact_id = edge.get("artifact_id")
    if not (isinstance(span, dict) and isinstance(artifact_id, str) and read_snapshot):
        return None
    offset = span.get("byte_offset")
    length = span.get("byte_length")
    if not (isinstance(offset, int) and isinstance(length, int) and offset >= 0 and length > 0):
        return None
    try:
        blob = read_snapshot(artifact_id)
    except Exception:
        return None
    chunk = blob[offset : offset + length]
    if len(chunk) != length:
        return None
    try:
        return chunk.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _build_authority_unit(claim, catalog, read_snapshot):
    """Build one authority unit for an admitted [Text] claim. Returns ``(unit, None)`` or
    ``(None, reason)``. This is the ONLY producer of AuthorityRenderUnit."""
    if claim.get("verification_state") != "runtime-validated":
        return None, TRACE_CLAIM_NOT_ADMITTED
    edges = claim.get("edges") or []
    if not edges:
        return None, TRACE_CLAIM_NOT_ADMITTED  # an admitted [Text] must keep >=1 validated edge
    edge = edges[0]
    if edge.get("verification_state") != "runtime-validated":
        return None, TRACE_CLAIM_NOT_ADMITTED
    seed = _seed_for(edge, catalog)
    if seed is not None and getattr(seed, "interpretation_only", False):
        # Curator-flagged interpretation-only (a cross-locus thematic cue / paraphrase, not a
        # source-bound quotation): it can never mint Surface-A authority. An admitted [Text] citing
        # it is a bypass — refuse here so finalization fails atomically (ADR 0004 §5).
        return None, TRACE_INTERPRETATION_ONLY
    if not _rights_ok(seed):
        return None, TRACE_RIGHTS_BLOCKED
    representation_kind, marker, reason = _resolve_representation(claim, seed)
    if reason:
        return None, reason
    if edge.get("evidence_type") == RENDER_AS_QUOTATION:
        text = _canonical_quotation_text(edge, read_snapshot)
        if text is None:
            return None, TRACE_TEXT_NOT_CANONICAL
        render_as = RENDER_AS_QUOTATION
        tier = edge.get("span_assurance_tier")
    else:
        # source-bound summary: a paraphrase, rendered explicitly as a summary, not a quotation.
        text = claim.get("text")
        if not (isinstance(text, str) and text):
            return None, TRACE_TEXT_NOT_CANONICAL
        render_as = RENDER_AS_SOURCE_BOUND_SUMMARY
        tier = None
    try:
        unit = AuthorityRenderUnit(
            claim_id=claim.get("claim_id"),
            render_as=render_as,
            text=text,
            attribution=_attribution(seed, edge),
            representation_kind=representation_kind,
            rendering_marker=marker,
            span_assurance_tier=tier,
            provenance=getattr(seed, "provenance", None) if seed is not None else None,
            mint=_AUTHORITY_MINT,
        )
    except Exception:
        return None, TRACE_NOT_FROM_BUILDER
    return unit, None


def validate_answer_input(answer, verified, decisions, catalog, read_snapshot):
    """Independent trace gate (ADR 0004 §5): re-derive each authority unit from source and compare.

    Raises :class:`FinalizationError` on the first untraceable / not-admitted / mismatched unit, so
    the caller fails atomically before any serialization. Operates on render units, never on prose.
    """
    by_id = {claim.get("claim_id"): claim for claim in verified.get("claims", [])}
    for unit in answer.authority_units:
        claim = by_id.get(unit.claim_id)
        if claim is None:
            raise FinalizationError(TRACE_UNKNOWN_CLAIM, unit.claim_id)
        decision = decisions.get(unit.claim_id)
        if not (decision and decision.get("decision") == "admit"):
            raise FinalizationError(TRACE_CLAIM_NOT_ADMITTED, unit.claim_id)
        if decision.get("render_as") != "text":
            raise FinalizationError(TRACE_RENDER_AS_DISALLOWED, unit.claim_id)
        expected, reason = _build_authority_unit(claim, catalog, read_snapshot)
        if expected is None:
            raise FinalizationError(reason or TRACE_TEXT_NOT_CANONICAL, unit.claim_id)
        if unit.render_as not in ALLOWED_AUTHORITY_RENDER_AS:
            raise FinalizationError(TRACE_RENDER_AS_DISALLOWED, unit.claim_id)
        if unit.text != expected.text:
            raise FinalizationError(TRACE_TEXT_NOT_CANONICAL, unit.claim_id)
        if unit.representation_kind != expected.representation_kind:
            raise FinalizationError(TRACE_REPRESENTATION_MISMATCH, unit.claim_id)
        if unit.rendering_marker != expected.rendering_marker:
            raise FinalizationError(TRACE_MARKER_MISSING, unit.claim_id)
        if unit.render_as != expected.render_as:
            raise FinalizationError(TRACE_RENDER_AS_DISALLOWED, unit.claim_id)


def serialize_surface_a(answer):
    """Deterministic Surface A text from authority units. No LLM; markers are program-added."""
    lines = []
    for unit in answer.authority_units:
        marker = " [{}]".format(unit.rendering_marker) if unit.rendering_marker else ""
        if unit.render_as == RENDER_AS_QUOTATION:
            lines.append("“{}” — {}{}".format(unit.text, unit.attribution, marker))
        else:
            lines.append("{} (source-bound summary — {}){}".format(unit.text, unit.attribution, marker))
    return "\n".join(lines)


def finalize(result, catalog, read_snapshot=None, *, speaker_id="council"):
    """Atomically finalize one panelist result into a :class:`FinalizedResponse`.

    Requires a B3 ``boundary_decision`` and a B2 ``claim_verification`` (the structured/strict
    path). Builds Surface A only from admitted [Text] claims; interpretation / unverified-citation
    claims go to Surface B (non-authoritative); rejected claims go to the audit channel only. Any
    bypass raises :class:`FinalizationError` and produces nothing.
    """
    verified = result.get("claim_verification")
    boundary = result.get("boundary_decision")
    if not isinstance(boundary, dict) or boundary.get("admitted") is None:
        raise FinalizationError(TRACE_NOT_FROM_BUILDER, "missing boundary_decision")
    if not isinstance(verified, dict):
        raise FinalizationError(TRACE_NOT_FROM_BUILDER, "missing claim_verification")

    if not boundary.get("admitted"):
        # Response-level deny (e.g. renderer-bypass / unsupported-protocol): nothing reaches A.
        audit = AuditRenderInput(
            AuditSummary((), tuple(r for r in (boundary.get("response_denial"),) if r)), ()
        )
        return FinalizedResponse(AnswerRenderInput((), ()), audit, surface_a="")

    decisions = {c.get("claim_id"): c for c in boundary.get("claims", [])}
    authority = []
    interpretation = []
    rejected = []
    reasons = set()
    for claim in verified.get("claims", []):
        cid = claim.get("claim_id")
        decision = decisions.get(cid)
        if not (decision and decision.get("decision") == "admit"):
            rejected.append(cid)
            if decision and decision.get("reason"):
                reasons.add(decision["reason"])
            continue
        claim_type = claim.get("claim_type")
        if claim_type == "text":
            if decision.get("render_as") != "text":
                raise FinalizationError(TRACE_RENDER_AS_DISALLOWED, "claim {}".format(cid))
            unit, reason = _build_authority_unit(claim, catalog, read_snapshot)
            if unit is None:
                # an admitted [Text] that cannot yield a canonical authority unit is a bypass
                raise FinalizationError(reason, "claim {}".format(cid))
            authority.append(unit)
        else:
            interpretation.append(
                InterpretationRenderUnit(
                    speaker_id=speaker_id,
                    content=claim.get("text", ""),
                    based_on_claim_ids=(),
                    kind="unverified-citation" if claim_type == "unverified-citation" else "interpretation",
                )
            )

    answer = AnswerRenderInput(tuple(authority), tuple(interpretation))
    # Independent gate BEFORE serialization -> atomic: a bypass raises and yields no Surface A.
    validate_answer_input(answer, verified, decisions, catalog, read_snapshot)
    surface_a = serialize_surface_a(answer)
    audit = AuditRenderInput(AuditSummary(tuple(rejected), tuple(sorted(reasons))), ())
    return FinalizedResponse(answer=answer, audit=audit, surface_a=surface_a)


def _unit_to_state(unit):
    # Excludes the capability token deliberately — it must never be serialized.
    return {
        "claim_id": unit.claim_id,
        "render_as": unit.render_as,
        "text": unit.text,
        "attribution": unit.attribution,
        "representation_kind": unit.representation_kind,
        "rendering_marker": unit.rendering_marker,
        "span_assurance_tier": unit.span_assurance_tier,
        "provenance": unit.provenance,
    }


def finalized_to_state(finalized):
    """JSON-serializable view of a :class:`FinalizedResponse` (drops the mint token)."""
    return {
        "surface_a": finalized.surface_a,
        "surface_b_frame": finalized.surface_b_frame,
        "answer": {
            "authority_units": [_unit_to_state(u) for u in finalized.answer.authority_units],
            "interpretation_units": [
                {
                    "speaker_id": i.speaker_id,
                    "content": i.content,
                    "based_on_claim_ids": list(i.based_on_claim_ids),
                    "kind": i.kind,
                }
                for i in finalized.answer.interpretation_units
            ],
        },
        "audit": {
            "rejected_claim_ids": list(finalized.audit.summary.rejected_claim_ids),
            "reason_codes": list(finalized.audit.summary.reason_codes),
        },
    }
