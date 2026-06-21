"""Deterministic, user-visible assurance footer for a finalized response (plan S4).

Strict finalization (ADR 0004) already produces the structured authority / audit state;
this helper exposes its *real* assurance level in a concise, deterministic form. Every
number is counted by code from the finalized state — never inferred from prose and never
produced by the LLM. The footer must not reinterpret policy or raise the apparent
assurance of anything: in particular it labels a span "edition-backed" only when the
finalized unit literally carries the edition-backed tier (which B2 never mints; reserved
for A2), so a curated-snapshot span can never be shown as edition-backed.

Input is the JSON-serializable view returned by ``render_finalizer.finalized_to_state``.
"""
from render_types import RENDER_AS_QUOTATION, RENDER_AS_SOURCE_BOUND_SUMMARY

# Span-assurance tier ids (mirrors policies/quote-admissibility.v2.json -> span_assurance_tiers;
# a drift test asserts membership in policy_enums.SPAN_ASSURANCE_TIERS).
CURATED_SNAPSHOT_TIER = "curated-snapshot-span-verified"
EDITION_BACKED_TIER = "edition-backed-span-verified"

# The non-removable Surface B residual limitation, always shown.
INTERPRETATION_LIMITATION = "non-authoritative / instruction-bounded"


def summarize_finalized(finalized_state):
    """Return the deterministic counts the footer renders (counted, never inferred).

    Buckets are mutually exclusive and exhaustive over the authority units, so
    ``curated + edition + span_unverified_quotation + source_bound_summaries`` always
    equals ``textual_claims_rendered``.
    """
    answer = finalized_state.get("answer") or {}
    authority = answer.get("authority_units") or []
    interpretation = answer.get("interpretation_units") or []
    audit = finalized_state.get("audit") or {}

    curated = 0
    edition = 0
    span_unverified_quotation = 0
    source_bound = 0
    representation_kinds = {}
    for unit in authority:
        render_as = unit.get("render_as")
        if render_as == RENDER_AS_QUOTATION:
            tier = unit.get("span_assurance_tier")
            if tier == CURATED_SNAPSHOT_TIER:
                curated += 1
            elif tier == EDITION_BACKED_TIER:
                edition += 1
            else:
                # A quotation that reached Surface A without a recognized verified tier is an
                # anomaly; surface it rather than silently counting it as verified.
                span_unverified_quotation += 1
        elif render_as == RENDER_AS_SOURCE_BOUND_SUMMARY:
            source_bound += 1
        representation = unit.get("representation_kind") or "(none)"
        representation_kinds[representation] = representation_kinds.get(representation, 0) + 1

    return {
        "textual_claims_rendered": len(authority),
        "curated_snapshot_span_verified": curated,
        "edition_backed_span_verified": edition,
        "span_unverified_quotation": span_unverified_quotation,
        "source_bound_summaries": source_bound,
        "denied_claims": len(audit.get("rejected_claim_ids") or []),
        "interpretation_units": len(interpretation),
        "representation_kinds": representation_kinds,
        "audit_reason_codes": list(audit.get("reason_codes") or []),
    }


def render_assurance_footer(finalized_state, *, expanded=False):
    """Render the deterministic assurance footer string for a finalized response.

    Concise by default; pass ``expanded=True`` for the audit view (representation-kind
    breakdown and audit reason codes — codes only, never the denied payload, which the
    finalized state does not carry). Output is stable and order-deterministic.
    """
    counts = summarize_finalized(finalized_state)
    lines = ["Authority assurance", "Mode: strict-finalized"]
    lines.append("Textual claims rendered: {}".format(counts["textual_claims_rendered"]))
    lines.append("Curated snapshot-span verified: {}".format(counts["curated_snapshot_span_verified"]))
    # Show the stronger / anomalous tiers only when actually present, so the footer never
    # implies the system mints an edition-backed span it did not produce.
    if counts["edition_backed_span_verified"]:
        lines.append("Edition-backed span verified: {}".format(counts["edition_backed_span_verified"]))
    if counts["span_unverified_quotation"]:
        lines.append("Quotation span not verified: {}".format(counts["span_unverified_quotation"]))
    lines.append("Source-bound summaries: {}".format(counts["source_bound_summaries"]))
    lines.append("Denied claims: {}".format(counts["denied_claims"]))
    # Surface B residual limitation is always visible.
    lines.append("Interpretation: {}".format(INTERPRETATION_LIMITATION))

    if expanded:
        if counts["representation_kinds"]:
            breakdown = ", ".join(
                "{}={}".format(kind, count)
                for kind, count in sorted(counts["representation_kinds"].items())
            )
            lines.append("  representation kinds: {}".format(breakdown))
        if counts["audit_reason_codes"]:
            lines.append("  audit reason codes: {}".format(", ".join(sorted(counts["audit_reason_codes"]))))
    return "\n".join(lines)
