"""Render-domain types for the renderer trust boundary (ADR 0004).

Pure data model — no controller, no I/O. The load-bearing rule is structural: no *supported*
public construction path mints an ``AuthorityRenderUnit`` (the only authority-bearing render
object) from raw prose or arbitrary text. It is minted only by the canonical authority builder,
which passes the module-private capability token; any other supported construction path raises.
This is a capability-shaped API guard, not a Python sandbox — an underscore name is not true
privacy, so same-process code could still introspect/monkeypatch. The actual security guarantee
comes from the builder + independent trace re-derivation + deterministic serializer + atomic
finalization (the threat model is a hostile moderator supplying DATA, not executing Python).
Authority is a property of provenance + render path (ADR 0004 §2/§6 invariant 2).

Surfaces:
* ``AuthorityRenderUnit`` — Surface A. Source-text presentation; minted only by the builder.
* ``InterpretationRenderUnit`` — Surface B. Freely constructible; carries NO ``[Text]`` authority.
* ``AuditSummary`` / ``AuditRenderInput`` — the audit channel (never fed to the answer renderer).
* ``AnswerRenderInput`` — what the ordinary answer renderer sees (A + B only; no denied payload).
* ``FinalizedResponse`` — the finalizer's atomic output.
"""
from dataclasses import dataclass, field
from typing import Any, Optional, Tuple

# Allowed authority render forms (a quotation or a source-bound summary; never raw prose).
RENDER_AS_QUOTATION = "quotation"
RENDER_AS_SOURCE_BOUND_SUMMARY = "source-bound-summary"
ALLOWED_AUTHORITY_RENDER_AS = frozenset({RENDER_AS_QUOTATION, RENDER_AS_SOURCE_BOUND_SUMMARY})

# Real render-time `renderer-bypass` sub-reasons (ADR 0004 §5). Distinct from B1b schema_status,
# B2 verification_state, and the controller-side boundary reasons.
TRACE_UNKNOWN_CLAIM = "trace-unknown-claim"
TRACE_CLAIM_NOT_ADMITTED = "trace-claim-not-admitted"
TRACE_RENDER_AS_DISALLOWED = "trace-render-as-disallowed"
TRACE_TEXT_NOT_CANONICAL = "trace-text-not-canonical"
TRACE_REPRESENTATION_MISMATCH = "trace-representation-mismatch"
TRACE_MARKER_MISSING = "trace-marker-missing"
TRACE_RIGHTS_BLOCKED = "trace-rights-blocked"
TRACE_NOT_FROM_BUILDER = "trace-not-from-builder"
# A seed the curator flagged interpretation_only (a cross-locus thematic cue / paraphrase, not a
# source-bound quotation) can never yield a Surface-A authority unit; an admitted [Text] citing it
# is a bypass, so finalization fails atomically (ADR 0004 §5).
TRACE_INTERPRETATION_ONLY = "trace-interpretation-only"
RENDERER_BYPASS_REASONS = frozenset(
    {
        TRACE_UNKNOWN_CLAIM,
        TRACE_CLAIM_NOT_ADMITTED,
        TRACE_RENDER_AS_DISALLOWED,
        TRACE_TEXT_NOT_CANONICAL,
        TRACE_REPRESENTATION_MISMATCH,
        TRACE_MARKER_MISSING,
        TRACE_RIGHTS_BLOCKED,
        TRACE_NOT_FROM_BUILDER,
        TRACE_INTERPRETATION_ONLY,
    }
)

# Non-removable Surface B frame (ADR 0004 §3/§6 invariant 7) — the serializer adds it, not the LLM.
INTERPRETATION_FRAME = "Council interpretation — not source text"


class RenderError(RuntimeError):
    """An authority unit was constructed without the canonical builder's capability token."""


class FinalizationError(RuntimeError):
    """Finalization failed atomically; no Surface A is produced (ADR 0004 §5)."""

    def __init__(self, reason, message=""):
        self.reason = reason
        super().__init__("{}: {}".format(reason, message) if message else str(reason))


# Capability token. Only the canonical authority builder imports and passes this.
_AUTHORITY_MINT = object()


@dataclass(frozen=True)
class AuthorityRenderUnit:
    """Surface A unit. Mint ONLY via the canonical builder (it passes ``mint=_AUTHORITY_MINT``).

    ``text`` is canonical: for a quotation it is the snapshot span bytes (not producer text);
    for a source-bound summary it is the producer paraphrase, rendered explicitly as a summary.
    ``representation_kind`` is system-authoritative or None — never a producer-raised claim.
    """

    claim_id: str
    render_as: str
    text: str
    attribution: str
    representation_kind: Optional[str] = None
    rendering_marker: Optional[str] = None
    span_assurance_tier: Optional[str] = None
    provenance: Optional[dict] = None
    mint: Any = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        if self.mint is not _AUTHORITY_MINT:
            raise RenderError(
                "AuthorityRenderUnit may only be created by the canonical authority builder"
            )
        if self.render_as not in ALLOWED_AUTHORITY_RENDER_AS:
            raise RenderError("disallowed render_as: {!r}".format(self.render_as))
        if not (isinstance(self.text, str) and self.text):
            raise RenderError("authority unit text must be a non-empty string")


@dataclass(frozen=True)
class InterpretationRenderUnit:
    """Surface B unit — analysis/argument. Carries no [Text] authority; freely constructible."""

    speaker_id: str
    content: str
    based_on_claim_ids: Tuple[str, ...] = ()
    kind: str = "interpretation"  # interpretation | unverified-citation (non-supporting)


@dataclass(frozen=True)
class AuditSummary:
    rejected_claim_ids: Tuple[str, ...] = ()
    reason_codes: Tuple[str, ...] = ()


@dataclass(frozen=True)
class AnswerRenderInput:
    """What the ordinary answer renderer sees: authority + interpretation, never denied payload."""

    authority_units: Tuple[AuthorityRenderUnit, ...] = ()
    interpretation_units: Tuple[InterpretationRenderUnit, ...] = ()


@dataclass(frozen=True)
class AuditRenderInput:
    """Separate type (not the answer input with fields deleted) to prevent accidental passthrough."""

    summary: AuditSummary = field(default_factory=AuditSummary)
    diagnostics: Tuple[dict, ...] = ()


@dataclass(frozen=True)
class FinalizedResponse:
    answer: AnswerRenderInput
    audit: AuditRenderInput
    surface_a: str
    surface_b_frame: str = INTERPRETATION_FRAME
