"""RetrievalEvidenceAdapterV1 (B1a) — retrieval envelope -> evidence seeds.

Consumes the versioned retrieval envelope (``religion-council/retrieval/v1``),
ingests each record's ``text`` as an immutable, content-addressed Artifact, and
emits one :class:`EvidenceSeed` per *occurrence*. Artifacts dedupe by bytes; seeds
never do (each carries its own ``occurrence_id``).

Scope (ADR 0002 B1 / ADR 0003): schema-level rejection only; ``verification_state``
is always ``"unverified"``. The adapter does NOT decide admissibility and does NOT
create Claims, ClaimEvidenceEdges, or VerificationResults — those are B1b (and
``evidentiary_role`` is claim-relative, so it cannot exist without a claim).
"""
import hashlib
from dataclasses import dataclass
from typing import Optional

import policy_enums
from claim_protocol import SchemaRejection

ACCEPTED_CONTRACT_VERSION = "religion-council/retrieval/v1"
_UNIT_SEP = "\x1f"

# Occurrence-identity schemes (ADR 0005). The scheme is recorded on each seed and in the origins
# log so persisted audit references stay reproducible and self-describing across backends.
OCCURRENCE_SCHEME_CORPUS_STABLE = "occ/v1-corpus-stable"    # source_file + source_line (file-based legacy)
OCCURRENCE_SCHEME_NETWORK_STABLE = "occ/v1-network-stable"  # content hash + stable key; order-independent
OCCURRENCE_SCHEME_INDEX_FALLBACK = "occ/v1-index-fallback"  # list position; retrieval-order scoped (stop-gap)

# Acquisition origins that obtain bytes dynamically (network / external capture) and therefore MUST
# NOT mint an order-dependent occurrence id (ADR 0005). Extend this set when new network origins land.
STABLE_IDENTITY_REQUIRED_ORIGINS = frozenset({"runtime-captured"})


class StableIdentityError(SchemaRejection):
    """A network/dynamic record reached the adapter without stable occurrence-identity inputs.

    Fail-closed (ADR 0005): rather than mint a retrieval-order-dependent occurrence id, the
    adapter rejects before any persistence and before claim binding. Subclasses SchemaRejection
    so the controller's existing fail-closed envelope handling catches it.
    """


@dataclass
class EvidenceSeed:
    occurrence_id: str
    artifact_id: str
    byte_offset: int
    byte_length: int
    artifact_kind: str
    acquisition_origin: str
    retrieval_path: str
    source_assurance: str
    verification_state: str
    # Producer-declared metadata: carried, never trusted (ADR 0003 §2).
    declared_label: Optional[str]
    declared_evidence_type: Optional[str]
    declared_verbatim: Optional[bool]
    # Which ADR-0005 scheme minted occurrence_id (explicit identity versioning, for audit).
    occurrence_id_scheme: Optional[str] = None
    # Carried context (not identity):
    tradition: Optional[str] = None
    work: Optional[str] = None
    locator: Optional[str] = None
    topic: Optional[str] = None
    language: Optional[str] = None
    retrieval_rank: Optional[int] = None
    source_file: Optional[str] = None
    source_line: Optional[int] = None
    # A1 curated presentation/provenance, carried-not-trusted (ADR 0003 §2). Present only when
    # the curation sidecar marks this record (e.g. a Chinese Qur'an snippet is a
    # published-translation + meaning-rendering); absent -> None. They are NOT inferred from the
    # record (language=zh-Hant alone cannot say a snippet is a rendering); B2 still span-verifies
    # and the renderer still shows a rendering marker — these are declared, not a verification.
    declared_representation_kind: Optional[str] = None
    declared_rendering_mode: Optional[str] = None
    provenance: Optional[dict] = None
    rights: Optional[str] = None


def artifact_kind_of(record):
    """Derive artifact_kind from evidence_type/verbatim — never from category."""
    evidence_type = record.get("evidence_type")
    verbatim = record.get("verbatim")
    if evidence_type == "quotation" and verbatim is True:
        return "source-text"
    if evidence_type == "source-bound-summary" and verbatim is False:
        return "reference-summary"
    return "unknown"


def _nonempty_str(value):
    return isinstance(value, str) and bool(value.strip())


def _has_origin_hints(record):
    # A legitimate file-based origin hint is a NON-EMPTY source path AND a POSITIVE line number.
    # Degenerate values (e.g. source_file="" / source_line=0, or a bool) are not hints and must
    # not let a network/dynamic record mint a corpus-stable id and slip past the fail-closed gate.
    source_line = record.get("source_line")
    return (
        _nonempty_str(record.get("source_file"))
        and isinstance(source_line, int)
        and not isinstance(source_line, bool)
        and source_line > 0
    )


def stable_occurrence_inputs_available(record):
    """True if ``record`` can yield an order-INDEPENDENT occurrence id (ADR 0005).

    Stable inputs are any of: file-based origin hints (``source_file`` + ``source_line``),
    an explicit backend-stable ``record_key``, or a ``(work, locator)`` pair that pins the
    occurrence. A record carrying only its list position is NOT stable.
    """
    if _has_origin_hints(record):
        return True
    if _nonempty_str(record.get("record_key")):
        return True
    return _nonempty_str(record.get("work")) and _nonempty_str(record.get("locator"))


def occurrence_scheme(record, acquisition_origin):
    """Pick the occurrence-identity scheme (ADR 0005) for this record + acquisition origin."""
    if _has_origin_hints(record):
        return OCCURRENCE_SCHEME_CORPUS_STABLE
    if acquisition_origin in STABLE_IDENTITY_REQUIRED_ORIGINS:
        return OCCURRENCE_SCHEME_NETWORK_STABLE
    return OCCURRENCE_SCHEME_INDEX_FALLBACK


def occurrence_id(record, artifact_id, record_index, *, acquisition_origin="bundled"):
    """Per-occurrence id; never the artifact_id alone. Scheme per ADR 0005.

    The same bytes can appear at different work/locator/source lines, so identity must not
    collapse to ``artifact_id``. Three schemes (the id bytes of the legacy two are unchanged):

    * **corpus-stable** (``source_file`` + ``source_line``, i.e. file-based A0/A1): excludes
      retrieval rank, so it is stable across queries. The documented file-based legacy.
    * **network-stable** (a ``STABLE_IDENTITY_REQUIRED_ORIGINS`` origin): order-INDEPENDENT,
      from the content hash plus a stable key (``record_key`` else ``work`` + ``locator``).
      The adapter guarantees those inputs exist by failing closed in :func:`adapt` first.
    * **index-fallback** (any other origin without hints): keyed on ``record_index`` and so
      **retrieval-order scoped**. A deliberate stop-gap; never used for network acquisition.
    """
    scheme = occurrence_scheme(record, acquisition_origin)
    work = str(record.get("work", ""))
    locator = str(record.get("locator", ""))
    if scheme == OCCURRENCE_SCHEME_CORPUS_STABLE:
        parts = [artifact_id, work, locator, str(record.get("source_file")), str(record.get("source_line"))]
    elif scheme == OCCURRENCE_SCHEME_NETWORK_STABLE:
        record_key = record.get("record_key")
        if _nonempty_str(record_key):
            parts = [artifact_id, "key:" + str(record_key)]
        else:  # adapt() guarantees work+locator are present for this scheme
            parts = [artifact_id, "wl:" + work, locator]
    else:
        parts = [
            artifact_id,
            "idx:{}".format(record_index),
            work,
            locator,
            str(record.get("topic", "")),
            str(record.get("tradition", "")),
        ]
    return hashlib.sha256(_UNIT_SEP.join(parts).encode("utf-8")).hexdigest()


def _require_text(record, index):
    text = record.get("text")
    if not isinstance(text, str):
        raise SchemaRejection(
            "record[{}].text must be a string, got {}".format(index, type(text).__name__)
        )
    # Reject the exact empty string only; whitespace-only text is canonicalized
    # (not trimmed), so it is a legitimate artifact.
    if text == "":
        raise SchemaRejection("record[{}].text must not be the empty string".format(index))
    return text


def adapt(envelope, store, *, acquisition_origin="bundled", retrieval_path="retrieved-via-seam"):
    """Adapt a retrieval envelope into EvidenceSeeds, persisting immutable snapshots.

    Schema-level rejection only. ``verification_state`` is always ``"unverified"``.
    """
    if not isinstance(envelope, dict):
        raise SchemaRejection("envelope must be an object")
    version = envelope.get("contract_version")
    if version != ACCEPTED_CONTRACT_VERSION:
        raise SchemaRejection("unsupported contract_version: {!r}".format(version))
    records = envelope.get("records")
    if not isinstance(records, list):
        raise SchemaRejection("envelope.records must be a list")
    if acquisition_origin not in policy_enums.ACQUISITION_ORIGINS:
        raise ValueError("invalid acquisition_origin: {!r}".format(acquisition_origin))
    if retrieval_path not in policy_enums.RETRIEVAL_PATHS:
        raise ValueError("invalid retrieval_path: {!r}".format(retrieval_path))

    # Preflight every record before any persistence side effect, so a schema-invalid
    # envelope leaves the store untouched (no partial snapshots / origins).
    require_stable_identity = acquisition_origin in STABLE_IDENTITY_REQUIRED_ORIGINS
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise SchemaRejection("record[{}] must be an object".format(index))
        _require_text(record, index)
        # A1 fail-closed (ADR 0005): a network/dynamic record must not mint an order-dependent id.
        if require_stable_identity and not stable_occurrence_inputs_available(record):
            raise StableIdentityError(
                "record[{}]: {} acquisition requires stable occurrence-identity inputs "
                "(record_key, or work+locator, or source_file+source_line); refusing an "
                "order-dependent occurrence id (ADR 0005).".format(index, acquisition_origin)
            )

    seeds = []
    for index, record in enumerate(records):
        text = _require_text(record, index)
        aid, byte_length = store.put_snapshot(text)
        occ = occurrence_id(record, aid, index, acquisition_origin=acquisition_origin)
        scheme = occurrence_scheme(record, acquisition_origin)
        seeds.append(
            EvidenceSeed(
                occurrence_id=occ,
                artifact_id=aid,
                byte_offset=0,
                byte_length=byte_length,
                artifact_kind=artifact_kind_of(record),
                acquisition_origin=acquisition_origin,
                retrieval_path=retrieval_path,
                source_assurance="artifact-backed",
                verification_state="unverified",
                occurrence_id_scheme=scheme,
                declared_label=record.get("label"),
                declared_evidence_type=record.get("evidence_type"),
                declared_verbatim=record.get("verbatim"),
                tradition=record.get("tradition"),
                work=record.get("work"),
                locator=record.get("locator"),
                topic=record.get("topic"),
                language=record.get("language"),
                retrieval_rank=index,
                source_file=record.get("source_file"),
                source_line=record.get("source_line"),
                declared_representation_kind=record.get("representation_kind"),
                declared_rendering_mode=record.get("rendering_mode"),
                provenance=record.get("provenance"),
                rights=record.get("rights"),
            )
        )
        store.append_origin(
            {
                "artifact_id": aid,
                "occurrence_id": occ,
                "occurrence_id_scheme": scheme,
                "tradition": record.get("tradition"),
                "work": record.get("work"),
                "locator": record.get("locator"),
                "topic": record.get("topic"),
                "source_file": record.get("source_file"),
                "source_line": record.get("source_line"),
                "retrieval_rank": index,
            }
        )
    return seeds
